#ifdef __linux__
#include "phoneview_ui.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <gtk/gtk.h>
#include <gdk/gdkx.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>

#ifdef MIN
# undef MIN
#endif
#ifdef MAX
# undef MAX
#endif
#ifdef CLAMP
# undef CLAMP
#endif

#include "util/log.h"

#include <SDL3/SDL.h>

#define PHONEVIEW_UI_TITLEBAR_HEIGHT 40
#define PHONEVIEW_UI_TOOLBAR_HEIGHT 44
#define PHONEVIEW_UI_OUTER_MARGIN 24
#define PHONEVIEW_UI_MIN_VIDEO_WIDTH 220
#define PHONEVIEW_UI_MIN_VIDEO_HEIGHT 300

struct sc_phoneview_ui {
    GtkWidget *window;

    GtkWidget *headerbar;
    GtkWidget *title_icon;
    GtkWidget *title_label;
    GtkWidget *title_project;
    GtkWidget *minimize_button;
    GtkWidget *maximize_button;
    GtkWidget *close_button;

    GtkWidget *toolbar;
    GtkWidget *edit_button;
    GtkWidget *add_button;
    GtkWidget *save_button;
    GtkWidget *done_button;
    GtkWidget *status_label;

    GtkWidget *video_area;
    GdkWindow *video_gdk_window;
    Window video_xid;
    SDL_Window *video_window;

    guint sync_timer_id;
    sc_phoneview_ui_action_cb action_cb;
    void *userdata;
    bool edit_mode;
    bool capture_mode;
    int add_type;
};

static void
phoneview_ui_emit(struct sc_phoneview_ui *ui,
                  enum sc_phoneview_ui_action action) {
    if (ui->action_cb) {
        ui->action_cb(action, ui->userdata);
    }
}

static GtkWidget *
phoneview_make_window_button(const char *label, const char *name) {
    GtkWidget *button = gtk_button_new_with_label(label);
    gtk_widget_set_name(button, name);
    gtk_widget_set_can_focus(button, FALSE);
    gtk_widget_set_valign(button, GTK_ALIGN_CENTER);
    gtk_widget_set_size_request(button, 34, 28);
    return button;
}

static GtkWidget *
phoneview_make_toolbar_button(const char *label,
                              const char *icon_name,
                              const char *name) {
    GtkWidget *image =
        gtk_image_new_from_icon_name(icon_name, GTK_ICON_SIZE_BUTTON);
    GtkWidget *button = gtk_button_new_with_label(label);

    gtk_button_set_image(GTK_BUTTON(button), image);
    gtk_button_set_always_show_image(GTK_BUTTON(button), TRUE);
    gtk_widget_set_name(button, name);
    gtk_widget_set_can_focus(button, FALSE);
    gtk_widget_set_valign(button, GTK_ALIGN_CENTER);

    return button;
}

static void
phoneview_ui_on_edit(GtkButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_EDIT);
}

static void
phoneview_ui_on_add(GtkToolButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_ADD);
}

static void
phoneview_ui_select_add_type(GtkWidget *menu_item, gpointer userdata) {
    struct sc_phoneview_ui *ui = userdata;
    if (!ui) {
        return;
    }

    ui->add_type = GPOINTER_TO_INT(
        g_object_get_data(G_OBJECT(menu_item), "phoneview-add-type"));
    phoneview_ui_emit(ui, SC_PHONEVIEW_UI_ACTION_ADD);
}

static GtkWidget *
phoneview_ui_make_add_menu(struct sc_phoneview_ui *ui) {
    GtkWidget *menu = gtk_menu_new();

    static const struct {
        int type;
        const char *label;
    } items[] = {
        {SC_PHONEVIEW_ADD_KEYBOARD, "Keyboard Key  •  Hold"},
        {SC_PHONEVIEW_ADD_TAP, "Keyboard Key  •  Tap"},
        {SC_PHONEVIEW_ADD_TOGGLE, "Keyboard Key  •  Toggle"},
        {SC_PHONEVIEW_ADD_MOUSE, "Mouse Button"},
        {SC_PHONEVIEW_ADD_LOOK, "Mouse Look / Camera"},
        {SC_PHONEVIEW_ADD_WHEEL, "Mouse Wheel"},
        {SC_PHONEVIEW_ADD_JOYSTICK, "Virtual Joystick  •  WASD"},
    };

    for (size_t i = 0; i < sizeof(items) / sizeof(items[0]); ++i) {
        GtkWidget *item = gtk_menu_item_new_with_label(items[i].label);
        g_object_set_data(G_OBJECT(item),
                          "phoneview-add-type",
                          GINT_TO_POINTER(items[i].type));
        g_signal_connect(item, "activate",
                         G_CALLBACK(phoneview_ui_select_add_type),
                         ui);
        gtk_menu_shell_append(GTK_MENU_SHELL(menu), item);
    }

    gtk_widget_show_all(menu);
    return menu;
}

static void
phoneview_ui_on_save(GtkButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_SAVE);
}

static void
phoneview_ui_on_done(GtkButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_DONE);
}

static void
phoneview_ui_on_minimize(GtkButton *button, gpointer userdata) {
    (void) button;

    struct sc_phoneview_ui *ui = userdata;
    if (ui && ui->window) {
        gtk_window_iconify(GTK_WINDOW(ui->window));
    }
}

static void
phoneview_ui_update_maximize_button(struct sc_phoneview_ui *ui) {
    if (!ui || !ui->maximize_button) {
        return;
    }

    bool maximized = gtk_window_is_maximized(GTK_WINDOW(ui->window));
    gtk_button_set_label(GTK_BUTTON(ui->maximize_button),
                         maximized ? "❐" : "□");
}

static void
phoneview_ui_on_maximize(GtkButton *button, gpointer userdata) {
    (void) button;

    struct sc_phoneview_ui *ui = userdata;
    if (!ui || !ui->window) {
        return;
    }

    if (gtk_window_is_maximized(GTK_WINDOW(ui->window))) {
        gtk_window_unmaximize(GTK_WINDOW(ui->window));
    } else {
        gtk_window_maximize(GTK_WINDOW(ui->window));
    }

    phoneview_ui_update_maximize_button(ui);
}

static void
phoneview_ui_on_close(GtkButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_CLOSE);
}

static gboolean
phoneview_ui_on_window_state(GtkWidget *widget,
                             GdkEventWindowState *event,
                             gpointer userdata) {
    (void) widget;
    (void) event;

    phoneview_ui_update_maximize_button(userdata);
    return FALSE;
}

static gboolean
phoneview_ui_on_delete_event(GtkWidget *widget,
                             GdkEvent *event,
                             gpointer userdata) {
    (void) widget;
    (void) event;

    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_CLOSE);
    return TRUE;
}

static bool
phoneview_ui_asset_path(const char *subpath,
                        const char *filename,
                        char *out,
                        size_t out_size) {
    char executable[PATH_MAX];
    ssize_t length = readlink("/proc/self/exe",
                              executable,
                              sizeof(executable) - 1);
    if (length <= 0 || (size_t) length >= sizeof(executable)) {
        return false;
    }

    executable[length] = '\0';

    char *slash = strrchr(executable, '/');
    if (!slash) {
        return false;
    }
    *slash = '\0';

    slash = strrchr(executable, '/');
    if (!slash) {
        return false;
    }
    *slash = '\0';

    int written = snprintf(out,
                           out_size,
                           "%s/share/%s/%s",
                           executable,
                           subpath,
                           filename);

    return written > 0 && (size_t) written < out_size;
}

static void
phoneview_ui_sync_video_size(struct sc_phoneview_ui *ui) {
    if (!ui || !ui->video_gdk_window || !ui->video_xid) {
        return;
    }

    int width = gtk_widget_get_allocated_width(ui->video_area);
    int height = gtk_widget_get_allocated_height(ui->video_area);
    if (width <= 0 || height <= 0) {
        return;
    }

    GdkDisplay *display = gtk_widget_get_display(ui->video_area);
    if (!display || !GDK_IS_X11_DISPLAY(display)) {
        return;
    }

    Display *xdisplay = gdk_x11_display_get_xdisplay(display);

    XMoveResizeWindow(xdisplay,
                      ui->video_xid,
                      0,
                      0,
                      (unsigned) width,
                      (unsigned) height);

    XMapRaised(xdisplay, ui->video_xid);
    XFlush(xdisplay);

}

static void
phoneview_ui_focus_video(struct sc_phoneview_ui *ui) {
    if (!ui || !ui->video_xid || !ui->window) {
        return;
    }

    GdkDisplay *display = gtk_widget_get_display(ui->window);
    if (!display || !GDK_IS_X11_DISPLAY(display)) {
        return;
    }

    Display *xdisplay = gdk_x11_display_get_xdisplay(display);
    XRaiseWindow(xdisplay, ui->video_xid);
    XSetInputFocus(xdisplay, ui->video_xid,
                   RevertToParent, CurrentTime);
    XFlush(xdisplay);
}

static gboolean
phoneview_ui_focus_video_idle(gpointer userdata) {
    struct sc_phoneview_ui *ui = userdata;
    if (!ui || !ui->capture_mode) {
        return G_SOURCE_REMOVE;
    }

    phoneview_ui_focus_video(ui);
    return G_SOURCE_REMOVE;
}

static gboolean
phoneview_ui_periodic_sync(gpointer userdata) {
    struct sc_phoneview_ui *ui = userdata;
    if (!ui || !ui->window || !ui->video_area) {
        return G_SOURCE_REMOVE;
    }

    phoneview_ui_sync_video_size(ui);
    return G_SOURCE_CONTINUE;
}

static void
phoneview_ui_on_video_allocate(GtkWidget *widget,
                               GdkRectangle *allocation,
                               gpointer userdata) {
    (void) widget;
    (void) allocation;

    phoneview_ui_sync_video_size(userdata);
}

static void
phoneview_ui_fit_initial_window(struct sc_phoneview_ui *ui,
                                int requested_video_width,
                                int requested_video_height) {
    if (!ui || !ui->window) {
        return;
    }

    GdkDisplay *display = gtk_widget_get_display(ui->window);
    if (!display) {
        return;
    }

    GdkMonitor *monitor = gdk_display_get_primary_monitor(display);
    if (!monitor) {
        return;
    }

    GdkRectangle workarea = {0};
    gdk_monitor_get_workarea(monitor, &workarea);

    const int chrome_height =
        PHONEVIEW_UI_TITLEBAR_HEIGHT + PHONEVIEW_UI_TOOLBAR_HEIGHT;

    const int available_width =
        MAX(320, workarea.width - PHONEVIEW_UI_OUTER_MARGIN);
    const int available_height =
        MAX(420, workarea.height - PHONEVIEW_UI_OUTER_MARGIN - chrome_height);

    int video_width = MAX(PHONEVIEW_UI_MIN_VIDEO_WIDTH,
                          requested_video_width);
    int video_height = MAX(PHONEVIEW_UI_MIN_VIDEO_HEIGHT,
                           requested_video_height);

    double scale_x = (double) available_width / (double) video_width;
    double scale_y = (double) available_height / (double) video_height;
    double scale = MIN(1.0, MIN(scale_x, scale_y));

    video_width = MAX(PHONEVIEW_UI_MIN_VIDEO_WIDTH,
                      (int) (video_width * scale));
    video_height = MAX(PHONEVIEW_UI_MIN_VIDEO_HEIGHT,
                       (int) (video_height * scale));

    gtk_window_set_default_size(GTK_WINDOW(ui->window),
                                video_width,
                                video_height + chrome_height);
    gtk_window_resize(GTK_WINDOW(ui->window),
                      video_width,
                      video_height + chrome_height);
}

static void
phoneview_ui_update_visibility(struct sc_phoneview_ui *ui) {
    if (!ui) {
        return;
    }

    /* Normal mode: show Edit only. Edit mode: show mapping actions. */
    gtk_widget_set_visible(ui->edit_button, !ui->edit_mode);
    gtk_widget_set_visible(ui->add_button, ui->edit_mode);
    gtk_widget_set_visible(ui->save_button, ui->edit_mode);
    gtk_widget_set_visible(ui->done_button, ui->edit_mode);
    gtk_widget_set_visible(ui->status_label, ui->edit_mode);

    gtk_widget_set_sensitive(ui->add_button, ui->edit_mode);
    gtk_widget_set_sensitive(ui->save_button, ui->edit_mode);
    gtk_widget_set_sensitive(ui->done_button, ui->edit_mode);

    GtkStyleContext *edit_style =
        gtk_widget_get_style_context(ui->edit_button);
    if (ui->edit_mode) {
        gtk_style_context_add_class(edit_style, "active");
    } else {
        gtk_style_context_remove_class(edit_style, "active");
    }

    if (!ui->edit_mode) {
        gtk_label_set_text(GTK_LABEL(ui->status_label), "");
    } else if (ui->capture_mode) {
        gtk_label_set_text(GTK_LABEL(ui->status_label),
                           "Waiting for input  •  Esc to cancel");
    } else {
        gtk_label_set_text(GTK_LABEL(ui->status_label),
                           "Control mapping");
    }
}

static void
phoneview_ui_apply_assets(struct sc_phoneview_ui *ui) {
    char icon_path[PATH_MAX];
    if (phoneview_ui_asset_path(
            "icons/hicolor/scalable/apps",
            "phoneview.svg",
            icon_path,
            sizeof(icon_path))) {
        gtk_window_set_icon_from_file(GTK_WINDOW(ui->window),
                                      icon_path,
                                      NULL);

        GError *icon_error = NULL;
        GdkPixbuf *pixbuf =
            gdk_pixbuf_new_from_file_at_scale(icon_path,
                                              20,
                                              20,
                                              TRUE,
                                              &icon_error);
        if (pixbuf) {
            gtk_image_set_from_pixbuf(GTK_IMAGE(ui->title_icon), pixbuf);
            g_object_unref(pixbuf);
        } else {
            LOGW("PhoneView UI: could not scale icon: %s",
                 icon_error ? icon_error->message : "unknown error");
            if (icon_error) {
                g_error_free(icon_error);
            }
        }

        gtk_widget_set_size_request(ui->title_icon, 20, 20);
        gtk_widget_set_halign(ui->title_icon, GTK_ALIGN_CENTER);
        gtk_widget_set_valign(ui->title_icon, GTK_ALIGN_CENTER);
    } else {
        LOGW("PhoneView UI: custom icon was not found");
    }

    char css_path[PATH_MAX];
    bool css_found =
        phoneview_ui_asset_path("phoneview",
                                "phoneview.css",
                                css_path,
                                sizeof(css_path));

    if (!css_found || access(css_path, R_OK) != 0) {
        css_found =
            phoneview_ui_asset_path(
                "icons/hicolor/scalable/apps",
                "phoneview.css",
                css_path,
                sizeof(css_path));
    }

    if (!css_found || access(css_path, R_OK) != 0) {
        LOGE("PhoneView UI: phoneview.css was not found");
        return;
    }

    LOGI("PhoneView UI: loading theme: %s", css_path);

    GtkCssProvider *provider = gtk_css_provider_new();
    GError *error = NULL;

    gtk_css_provider_load_from_path(provider, css_path, &error);
    if (error) {
        LOGE("PhoneView UI: failed to load CSS '%s': %s",
             css_path,
             error->message);
        g_error_free(error);
        g_object_unref(provider);
        return;
    }

    GdkScreen *style_screen = gtk_widget_get_screen(ui->window);
    gtk_style_context_add_provider_for_screen(
        style_screen,
        GTK_STYLE_PROVIDER(provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(provider);
}

struct sc_phoneview_ui *
sc_phoneview_ui_create(const char *title,
                       int video_width,
                       int video_height,
                       bool always_on_top,
                       bool decorated,
                       sc_phoneview_ui_action_cb action_cb,
                       void *userdata) {
    (void) decorated;

    if (!gtk_init_check(NULL, NULL)) {
        LOGE("PhoneView UI: GTK could not initialize");
        return NULL;
    }

    GdkDisplay *display = gdk_display_get_default();
    if (!display || !GDK_IS_X11_DISPLAY(display)) {
        LOGE("PhoneView UI requires an X11 desktop session");
        return NULL;
    }

    struct sc_phoneview_ui *ui = calloc(1, sizeof(*ui));
    if (!ui) {
        LOG_OOM();
        return NULL;
    }

    ui->action_cb = action_cb;
    ui->userdata = userdata;

    ui->window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(ui->window), "PhoneView");
    gtk_window_set_decorated(GTK_WINDOW(ui->window), TRUE);
    gtk_window_set_resizable(GTK_WINDOW(ui->window), TRUE);

    if (always_on_top) {
        gtk_window_set_keep_above(GTK_WINDOW(ui->window), TRUE);
    }

    g_signal_connect(ui->window,
                     "delete-event",
                     G_CALLBACK(phoneview_ui_on_delete_event),
                     ui);
    g_signal_connect(ui->window,
                     "window-state-event",
                     G_CALLBACK(phoneview_ui_on_window_state),
                     ui);

    ui->headerbar = gtk_header_bar_new();
    gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(ui->headerbar), FALSE);
    gtk_widget_set_name(ui->headerbar, "phoneview-titlebar");
    gtk_widget_set_size_request(ui->headerbar, -1,
                                PHONEVIEW_UI_TITLEBAR_HEIGHT);

    GtkWidget *title_box =
        gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 7);
    gtk_widget_set_valign(title_box, GTK_ALIGN_CENTER);

    ui->title_icon = gtk_image_new();
    ui->title_label = gtk_label_new("PhoneView");
    ui->title_project =
        gtk_label_new(title && title[0] ? title : "Android Viewer");

    gtk_widget_set_name(ui->title_label, "phoneview-title");
    gtk_widget_set_name(ui->title_project, "phoneview-project");
    gtk_label_set_xalign(GTK_LABEL(ui->title_label), 0.f);
    gtk_label_set_xalign(GTK_LABEL(ui->title_project), 0.f);

    gtk_box_pack_start(GTK_BOX(title_box),
                       ui->title_icon,
                       FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(title_box),
                       ui->title_label,
                       FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(title_box),
                       ui->title_project,
                       FALSE, FALSE, 0);

    gtk_header_bar_set_custom_title(GTK_HEADER_BAR(ui->headerbar),
                                    title_box);

    ui->minimize_button =
        phoneview_make_window_button("—",
                                     "phoneview-window-minimize");
    ui->maximize_button =
        phoneview_make_window_button("□",
                                     "phoneview-window-maximize");
    ui->close_button =
        phoneview_make_window_button("×",
                                     "phoneview-window-close");

    gtk_header_bar_pack_end(GTK_HEADER_BAR(ui->headerbar),
                            ui->close_button);
    gtk_header_bar_pack_end(GTK_HEADER_BAR(ui->headerbar),
                            ui->maximize_button);
    gtk_header_bar_pack_end(GTK_HEADER_BAR(ui->headerbar),
                            ui->minimize_button);

    g_signal_connect(ui->minimize_button,
                     "clicked",
                     G_CALLBACK(phoneview_ui_on_minimize),
                     ui);
    g_signal_connect(ui->maximize_button,
                     "clicked",
                     G_CALLBACK(phoneview_ui_on_maximize),
                     ui);
    g_signal_connect(ui->close_button,
                     "clicked",
                     G_CALLBACK(phoneview_ui_on_close),
                     ui);

    gtk_window_set_titlebar(GTK_WINDOW(ui->window), ui->headerbar);

    GtkWidget *root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_container_add(GTK_CONTAINER(ui->window), root);

    ui->toolbar = gtk_toolbar_new();
    gtk_toolbar_set_style(GTK_TOOLBAR(ui->toolbar), GTK_TOOLBAR_BOTH_HORIZ);
    gtk_toolbar_set_icon_size(GTK_TOOLBAR(ui->toolbar), GTK_ICON_SIZE_MENU);
    gtk_widget_set_name(ui->toolbar, "phoneview-toolbar");
    gtk_widget_set_size_request(ui->toolbar, -1,
                                PHONEVIEW_UI_TOOLBAR_HEIGHT);
    gtk_box_pack_start(GTK_BOX(root), ui->toolbar,
                       FALSE, FALSE, 0);

    GtkToolItem *edit_item = gtk_tool_item_new();
    GtkToolItem *save_item = gtk_tool_item_new();
    GtkToolItem *done_item = gtk_tool_item_new();

    ui->edit_button =
        phoneview_make_toolbar_button("Edit",
                                       "document-edit-symbolic",
                                       "phoneview-edit-button");

    ui->add_button =
        GTK_WIDGET(gtk_menu_tool_button_new(
            gtk_image_new_from_icon_name("list-add-symbolic",
                                         GTK_ICON_SIZE_BUTTON),
            "Add Button"));
    gtk_menu_tool_button_set_menu(
        GTK_MENU_TOOL_BUTTON(ui->add_button),
        phoneview_ui_make_add_menu(ui));
    gtk_widget_set_name(ui->add_button, "phoneview-add-button");
    gtk_widget_set_valign(ui->add_button, GTK_ALIGN_CENTER);
    gtk_widget_set_can_focus(ui->add_button, FALSE);

    ui->save_button =
        phoneview_make_toolbar_button("Save",
                                       "document-save-symbolic",
                                       "phoneview-save-button");
    ui->done_button =
        phoneview_make_toolbar_button("Done",
                                       "emblem-ok-symbolic",
                                       "phoneview-done-button");

    gtk_container_add(GTK_CONTAINER(edit_item), ui->edit_button);
    gtk_container_add(GTK_CONTAINER(save_item), ui->save_button);
    gtk_container_add(GTK_CONTAINER(done_item), ui->done_button);

    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), edit_item, -1);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar),
                       GTK_TOOL_ITEM(ui->add_button), -1);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar),
                       gtk_separator_tool_item_new(),
                       -1);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), save_item, -1);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), done_item, -1);

    GtkToolItem *status_item = gtk_tool_item_new();
    gtk_tool_item_set_expand(status_item, TRUE);
    ui->status_label = gtk_label_new("");
    gtk_label_set_xalign(GTK_LABEL(ui->status_label), 1.f);
    gtk_widget_set_name(ui->status_label, "phoneview-status");
    gtk_container_add(GTK_CONTAINER(status_item), ui->status_label);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), status_item, -1);

    g_signal_connect(ui->edit_button,
                     "clicked",
                     G_CALLBACK(phoneview_ui_on_edit),
                     ui);
    g_signal_connect(ui->add_button,
                     "clicked",
                     G_CALLBACK(phoneview_ui_on_add),
                     ui);
    g_signal_connect(ui->save_button,
                     "clicked",
                     G_CALLBACK(phoneview_ui_on_save),
                     ui);
    g_signal_connect(ui->done_button,
                     "clicked",
                     G_CALLBACK(phoneview_ui_on_done),
                     ui);

    ui->video_area = gtk_drawing_area_new();
    gtk_widget_set_name(ui->video_area, "phoneview-video");
    gtk_widget_set_hexpand(ui->video_area, TRUE);
    gtk_widget_set_vexpand(ui->video_area, TRUE);
    gtk_widget_set_can_focus(ui->video_area, TRUE);
    gtk_widget_set_hexpand(ui->video_area, TRUE);
    gtk_widget_set_vexpand(ui->video_area, TRUE);
    gtk_widget_set_margin_start(ui->video_area, 0);
    gtk_widget_set_margin_end(ui->video_area, 0);
    gtk_widget_set_margin_top(ui->video_area, 0);
    gtk_widget_set_margin_bottom(ui->video_area, 0);
    gtk_widget_set_size_request(ui->video_area,
                                PHONEVIEW_UI_MIN_VIDEO_WIDTH,
                                PHONEVIEW_UI_MIN_VIDEO_HEIGHT);

    gtk_box_pack_start(GTK_BOX(root), ui->video_area,
                       TRUE, TRUE, 0);

    g_signal_connect(ui->video_area,
                     "size-allocate",
                     G_CALLBACK(phoneview_ui_on_video_allocate),
                     ui);

    phoneview_ui_apply_assets(ui);

    gtk_widget_show_all(ui->window);
    gtk_widget_realize(ui->window);
    gtk_widget_realize(ui->video_area);

    phoneview_ui_fit_initial_window(ui,
                                    video_width,
                                    video_height);

    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }

    ui->video_gdk_window = gtk_widget_get_window(ui->video_area);
    if (!ui->video_gdk_window) {
        LOGE("PhoneView UI: failed to realize the video surface");
        sc_phoneview_ui_destroy(ui);
        return NULL;
    }

    /*
     * GTK owns the placeholder area. SDL renders into a dedicated X11 child
     * created by PhoneView, avoiding geometry conflicts with GTK's child.
     */
    Window parent_xid = gdk_x11_window_get_xid(ui->video_gdk_window);
    Display *xdisplay = gdk_x11_display_get_xdisplay(display);

    ui->video_xid = XCreateSimpleWindow(
        xdisplay,
        parent_xid,
        0,
        0,
        (unsigned) MAX(1, video_width),
        (unsigned) MAX(1, video_height),
        0,
        0,
        0
    );
    if (!ui->video_xid) {
        LOGE("PhoneView UI: failed to create native video child window");
        sc_phoneview_ui_destroy(ui);
        return NULL;
    }

    XSelectInput(xdisplay,
                 ui->video_xid,
                 ExposureMask | StructureNotifyMask);
    XMapRaised(xdisplay, ui->video_xid);
    XFlush(xdisplay);

    SDL_PropertiesID props = SDL_CreateProperties();
    if (!props) {
        LOGE("PhoneView UI: SDL_CreateProperties() failed: %s",
             SDL_GetError());
        XDestroyWindow(xdisplay, ui->video_xid);
        ui->video_xid = 0;
        sc_phoneview_ui_destroy(ui);
        return NULL;
    }

    SDL_SetNumberProperty(props,
                          SDL_PROP_WINDOW_CREATE_X11_WINDOW_NUMBER,
                          (Sint64) ui->video_xid);

    ui->video_window = SDL_CreateWindowWithProperties(props);
    SDL_DestroyProperties(props);

    if (!ui->video_window) {
        LOGE("PhoneView UI: SDL_CreateWindowWithProperties() failed: %s",
             SDL_GetError());
        XDestroyWindow(xdisplay, ui->video_xid);
        ui->video_xid = 0;
        sc_phoneview_ui_destroy(ui);
        return NULL;
    }

    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }

    phoneview_ui_sync_video_size(ui);
    phoneview_ui_update_maximize_button(ui);

    ui->sync_timer_id =
        g_timeout_add(60, phoneview_ui_periodic_sync, ui);

    sc_phoneview_ui_set_edit_mode(ui, false);
    sc_phoneview_ui_set_capture_mode(ui, false);

    return ui;
}

void
sc_phoneview_ui_destroy(struct sc_phoneview_ui *ui) {
    if (!ui) {
        return;
    }

    if (ui->sync_timer_id) {
        g_source_remove(ui->sync_timer_id);
        ui->sync_timer_id = 0;
    }

    if (ui->video_window) {
        SDL_DestroyWindow(ui->video_window);
        ui->video_window = NULL;
    }

    if (ui->video_xid) {
        GdkDisplay *display = ui->window
            ? gtk_widget_get_display(ui->window)
            : NULL;
        if (display && GDK_IS_X11_DISPLAY(display)) {
            Display *xdisplay = gdk_x11_display_get_xdisplay(display);
            XDestroyWindow(xdisplay, ui->video_xid);
            XFlush(xdisplay);
        }
        ui->video_xid = 0;
    }

    if (ui->window) {
        gtk_widget_destroy(ui->window);
        ui->window = NULL;
    }

    free(ui);
}

SDL_Window *
sc_phoneview_ui_get_video_window(struct sc_phoneview_ui *ui) {
    return ui ? ui->video_window : NULL;
}

void
sc_phoneview_ui_show(struct sc_phoneview_ui *ui) {
    if (!ui || !ui->window) {
        return;
    }

    gtk_widget_show_all(ui->window);
    gtk_window_present(GTK_WINDOW(ui->window));

    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }

    phoneview_ui_sync_video_size(ui);
    gtk_widget_grab_focus(ui->video_area);
}

void
sc_phoneview_ui_hide(struct sc_phoneview_ui *ui) {
    if (ui && ui->window) {
        gtk_widget_hide(ui->window);
    }
}

void
sc_phoneview_ui_get_video_size(struct sc_phoneview_ui *ui,
                               int *width,
                               int *height) {
    if (width) {
        *width = 0;
    }
    if (height) {
        *height = 0;
    }

    if (!ui || !ui->video_area) {
        return;
    }

    if (width) {
        *width = gtk_widget_get_allocated_width(ui->video_area);
    }
    if (height) {
        *height = gtk_widget_get_allocated_height(ui->video_area);
    }
}

void
sc_phoneview_ui_set_window_size(struct sc_phoneview_ui *ui,
                                int video_width,
                                int video_height) {
    if (!ui || !ui->window) {
        return;
    }

    /*
     * scrcpy may request a portrait window larger than the current monitor.
     * Fit the requested video dimensions to the available work area while
     * preserving the phone aspect ratio.
     */
    phoneview_ui_fit_initial_window(ui, video_width, video_height);

    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }

    phoneview_ui_sync_video_size(ui);
}

void
sc_phoneview_ui_set_window_position(struct sc_phoneview_ui *ui,
                                    int x,
                                    int y) {
    if (ui && ui->window) {
        gtk_window_move(GTK_WINDOW(ui->window), x, y);
    }
}

void
sc_phoneview_ui_set_fullscreen(struct sc_phoneview_ui *ui,
                               bool fullscreen) {
    if (!ui || !ui->window) {
        return;
    }

    if (fullscreen) {
        gtk_window_fullscreen(GTK_WINDOW(ui->window));
    } else {
        gtk_window_unfullscreen(GTK_WINDOW(ui->window));
    }

    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }

    phoneview_ui_sync_video_size(ui);
}


static void
phoneview_dialog_add_row(GtkGrid *grid,
                         int row,
                         const char *caption,
                         GtkWidget *value) {
    GtkWidget *label = gtk_label_new(caption);
    gtk_label_set_xalign(GTK_LABEL(label), 0.f);
    gtk_grid_attach(grid, label, 0, row, 1, 1);
    gtk_grid_attach(grid, value, 1, row, 2, 1);
}

static GtkWidget *
phoneview_dialog_entry(const char *value) {
    GtkWidget *entry = gtk_entry_new();
    gtk_entry_set_text(GTK_ENTRY(entry), value ? value : "");
    gtk_entry_set_width_chars(GTK_ENTRY(entry), 22);
    return entry;
}

static GtkWidget *
phoneview_dialog_behavior_combo(const char *behavior) {
    GtkWidget *combo = gtk_combo_box_text_new();
    gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(combo), "hold", "Hold");
    gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(combo), "tap", "Tap");
    gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(combo), "toggle", "Toggle");

    if (behavior && !strcmp(behavior, "tap")) {
        gtk_combo_box_set_active_id(GTK_COMBO_BOX(combo), "tap");
    } else if (behavior && !strcmp(behavior, "toggle")) {
        gtk_combo_box_set_active_id(GTK_COMBO_BOX(combo), "toggle");
    } else {
        gtk_combo_box_set_active_id(GTK_COMBO_BOX(combo), "hold");
    }

    return combo;
}

static void
phoneview_dialog_set_key_hint(GtkGrid *grid, int row) {
    GtkWidget *hint = gtk_label_new(
        "Key names use SDL names, e.g. W, Space, Enter, Shift, Ctrl.");
    gtk_label_set_xalign(GTK_LABEL(hint), 0.f);
    gtk_widget_set_margin_top(hint, 4);
    gtk_grid_attach(grid, hint, 1, row, 2, 1);
}

bool
sc_phoneview_ui_edit_control(struct sc_phoneview_ui *ui,
                             struct sc_phoneview_control_edit *control) {
    if (!control) {
        return false;
    }

    GtkWindow *parent = ui && ui->window ? GTK_WINDOW(ui->window) : NULL;
    GtkWidget *dialog = gtk_dialog_new_with_buttons(
        "Edit PhoneView Control",
        parent,
        GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "_Cancel", GTK_RESPONSE_CANCEL,
        "_Apply", GTK_RESPONSE_ACCEPT,
        NULL);

    gtk_window_set_resizable(GTK_WINDOW(dialog), FALSE);
    gtk_window_set_default_size(GTK_WINDOW(dialog), 460, -1);

    GtkWidget *content = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    GtkWidget *outer = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_widget_set_margin_start(outer, 18);
    gtk_widget_set_margin_end(outer, 18);
    gtk_widget_set_margin_top(outer, 16);
    gtk_widget_set_margin_bottom(outer, 16);
    gtk_container_add(GTK_CONTAINER(content), outer);

    char type_text[64];
    if (!strcmp(control->type, "joystick")) {
        snprintf(type_text, sizeof(type_text), "Virtual Joystick");
    } else if (!strcmp(control->type, "keyboard")) {
        snprintf(type_text, sizeof(type_text), "Keyboard Button");
    } else if (!strcmp(control->type, "look")) {
        snprintf(type_text, sizeof(type_text), "Mouse Look / Camera");
    } else if (!strcmp(control->type, "mouse")) {
        snprintf(type_text, sizeof(type_text), "Mouse Button");
    } else if (!strcmp(control->type, "wheel")) {
        snprintf(type_text, sizeof(type_text), "Mouse Wheel");
    } else {
        snprintf(type_text, sizeof(type_text), "%s", control->type);
    }

    GtkWidget *heading = gtk_label_new(type_text);
    gtk_label_set_xalign(GTK_LABEL(heading), 0.f);
    gtk_widget_set_name(heading, "phoneview-editor-heading");
    gtk_box_pack_start(GTK_BOX(outer), heading, FALSE, FALSE, 0);

    GtkWidget *grid = gtk_grid_new();
    gtk_grid_set_row_spacing(GTK_GRID(grid), 8);
    gtk_grid_set_column_spacing(GTK_GRID(grid), 10);
    gtk_box_pack_start(GTK_BOX(outer), grid, FALSE, FALSE, 0);

    GtkWidget *label_entry = phoneview_dialog_entry(control->label);
    phoneview_dialog_add_row(GTK_GRID(grid), 0, "Label", label_entry);

    GtkWidget *behavior_combo = NULL;
    int row = 1;
    if (strcmp(control->type, "joystick")
            && strcmp(control->type, "wheel")) {
        behavior_combo = phoneview_dialog_behavior_combo(control->behavior);
        phoneview_dialog_add_row(GTK_GRID(grid), row++, "Behavior",
                                 behavior_combo);
    }

    GtkWidget *key_entry = NULL;
    GtkWidget *mouse_entry = NULL;
    GtkWidget *up_entry = NULL;
    GtkWidget *left_entry = NULL;
    GtkWidget *down_entry = NULL;
    GtkWidget *right_entry = NULL;

    if (!strcmp(control->type, "keyboard")) {
        key_entry = phoneview_dialog_entry(control->key);
        phoneview_dialog_add_row(GTK_GRID(grid), row++, "Key", key_entry);
        phoneview_dialog_set_key_hint(GTK_GRID(grid), row++);
    } else if (!strcmp(control->type, "joystick")) {
        up_entry = phoneview_dialog_entry(control->up_key);
        left_entry = phoneview_dialog_entry(control->left_key);
        down_entry = phoneview_dialog_entry(control->down_key);
        right_entry = phoneview_dialog_entry(control->right_key);
        phoneview_dialog_add_row(GTK_GRID(grid), row++, "Up", up_entry);
        phoneview_dialog_add_row(GTK_GRID(grid), row++, "Left", left_entry);
        phoneview_dialog_add_row(GTK_GRID(grid), row++, "Down", down_entry);
        phoneview_dialog_add_row(GTK_GRID(grid), row++, "Right", right_entry);
        phoneview_dialog_set_key_hint(GTK_GRID(grid), row++);
    } else if (!strcmp(control->type, "mouse")
               || !strcmp(control->type, "look")) {
        mouse_entry = phoneview_dialog_entry(control->mouse_button);
        phoneview_dialog_add_row(GTK_GRID(grid), row++, "Mouse Button",
                                 mouse_entry);
    } else if (!strcmp(control->type, "wheel")) {
        mouse_entry = phoneview_dialog_entry(control->mouse_button);
        gtk_widget_set_sensitive(mouse_entry, FALSE);
        phoneview_dialog_add_row(GTK_GRID(grid), row++, "Wheel Direction",
                                 mouse_entry);
    }

    GtkWidget *position_hint = gtk_label_new(
        "Drag the control on the phone screen to change its position.");
    gtk_label_set_xalign(GTK_LABEL(position_hint), 0.f);
    gtk_widget_set_margin_top(position_hint, 4);
    gtk_box_pack_start(GTK_BOX(outer), position_hint, FALSE, FALSE, 0);

    gtk_widget_show_all(dialog);
    gint response = gtk_dialog_run(GTK_DIALOG(dialog));

    bool apply = response == GTK_RESPONSE_ACCEPT;
    if (apply) {
        const char *text = gtk_entry_get_text(GTK_ENTRY(label_entry));
        if (text && text[0]) {
            snprintf(control->label, sizeof(control->label), "%s", text);
        }

        if (behavior_combo) {
            const char *id =
                gtk_combo_box_get_active_id(GTK_COMBO_BOX(behavior_combo));
            if (id && id[0]) {
                snprintf(control->behavior, sizeof(control->behavior),
                         "%s", id);
            }
        }

        if (key_entry) {
            const char *value = gtk_entry_get_text(GTK_ENTRY(key_entry));
            if (value && value[0]) {
                snprintf(control->key, sizeof(control->key), "%s", value);
            } else {
                apply = false;
            }
        }

        if (up_entry && left_entry && down_entry && right_entry) {
            const char *up = gtk_entry_get_text(GTK_ENTRY(up_entry));
            const char *left = gtk_entry_get_text(GTK_ENTRY(left_entry));
            const char *down = gtk_entry_get_text(GTK_ENTRY(down_entry));
            const char *right = gtk_entry_get_text(GTK_ENTRY(right_entry));
            if (!up[0] || !left[0] || !down[0] || !right[0]) {
                apply = false;
            } else {
                snprintf(control->up_key, sizeof(control->up_key), "%s", up);
                snprintf(control->left_key, sizeof(control->left_key), "%s", left);
                snprintf(control->down_key, sizeof(control->down_key), "%s", down);
                snprintf(control->right_key, sizeof(control->right_key), "%s", right);
            }
        }

        if (mouse_entry && strcmp(control->type, "wheel")) {
            const char *value = gtk_entry_get_text(GTK_ENTRY(mouse_entry));
            if (value && value[0]) {
                snprintf(control->mouse_button,
                         sizeof(control->mouse_button), "%s", value);
            }
        }
    }

    gtk_widget_destroy(dialog);
    return apply;
}

void
sc_phoneview_ui_set_edit_mode(struct sc_phoneview_ui *ui,
                              bool edit_mode) {
    if (!ui) {
        return;
    }

    ui->edit_mode = edit_mode;
    phoneview_ui_update_visibility(ui);
}

void
sc_phoneview_ui_set_capture_mode(struct sc_phoneview_ui *ui,
                                 bool capture_mode) {
    if (!ui) {
        return;
    }

    ui->capture_mode = capture_mode;
    phoneview_ui_update_visibility(ui);

    if (capture_mode) {
        if (ui->video_area) {
            gtk_widget_grab_focus(ui->video_area);
        }

        phoneview_ui_focus_video(ui);
        g_idle_add(phoneview_ui_focus_video_idle, ui);
    }
}

int
sc_phoneview_ui_get_add_type(struct sc_phoneview_ui *ui) {
    return ui ? ui->add_type : SC_PHONEVIEW_ADD_KEYBOARD;
}

void
sc_phoneview_ui_set_capture_status(struct sc_phoneview_ui *ui,
                                    const char *status) {
    if (!ui || !ui->status_label) {
        return;
    }

    gtk_label_set_text(GTK_LABEL(ui->status_label),
                       status ? status : "");
}

bool
sc_phoneview_ui_is_edit_mode(struct sc_phoneview_ui *ui) {
    return ui && ui->edit_mode;
}

int
sc_phoneview_ui_get_toolbar_height(struct sc_phoneview_ui *ui) {
    (void) ui;
    return PHONEVIEW_UI_TOOLBAR_HEIGHT;
}

void
sc_phoneview_ui_pump_events(struct sc_phoneview_ui *ui) {
    if (!ui) {
        return;
    }

    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }
}

#else

#include "phoneview_ui.h"
#include <stdlib.h>

struct sc_phoneview_ui {
    int unused;
};

struct sc_phoneview_ui *
sc_phoneview_ui_create(const char *title,
                       int video_width,
                       int video_height,
                       bool always_on_top,
                       bool decorated,
                       sc_phoneview_ui_action_cb action_cb,
                       void *userdata) {
    (void) title;
    (void) video_width;
    (void) video_height;
    (void) always_on_top;
    (void) decorated;
    (void) action_cb;
    (void) userdata;
    return NULL;
}

void
sc_phoneview_ui_destroy(struct sc_phoneview_ui *ui) {
    free(ui);
}

SDL_Window *
sc_phoneview_ui_get_video_window(struct sc_phoneview_ui *ui) {
    (void) ui;
    return NULL;
}

void
sc_phoneview_ui_show(struct sc_phoneview_ui *ui) {
    (void) ui;
}

void
sc_phoneview_ui_hide(struct sc_phoneview_ui *ui) {
    (void) ui;
}

void
sc_phoneview_ui_get_video_size(struct sc_phoneview_ui *ui,
                               int *width,
                               int *height) {
    (void) ui;
    if (width) {
        *width = 0;
    }
    if (height) {
        *height = 0;
    }
}

void
sc_phoneview_ui_set_window_size(struct sc_phoneview_ui *ui,
                                int video_width,
                                int video_height) {
    (void) ui;
    (void) video_width;
    (void) video_height;
}

void
sc_phoneview_ui_set_window_position(struct sc_phoneview_ui *ui,
                                    int x,
                                    int y) {
    (void) ui;
    (void) x;
    (void) y;
}

void
sc_phoneview_ui_set_fullscreen(struct sc_phoneview_ui *ui,
                               bool fullscreen) {
    (void) ui;
    (void) fullscreen;
}

void
sc_phoneview_ui_set_edit_mode(struct sc_phoneview_ui *ui,
                               bool edit_mode) {
    (void) ui;
    (void) edit_mode;
}

void
sc_phoneview_ui_set_capture_mode(struct sc_phoneview_ui *ui,
                                 bool capture_mode) {
    (void) ui;
    (void) capture_mode;
}

int
sc_phoneview_ui_get_add_type(struct sc_phoneview_ui *ui) {
    (void) ui;
    return SC_PHONEVIEW_ADD_KEYBOARD;
}

void
sc_phoneview_ui_set_capture_status(struct sc_phoneview_ui *ui,
                                    const char *status) {
    (void) ui;
    (void) status;
}

bool
sc_phoneview_ui_is_edit_mode(struct sc_phoneview_ui *ui) {
    (void) ui;
    return false;
}

int
sc_phoneview_ui_get_toolbar_height(struct sc_phoneview_ui *ui) {
    (void) ui;
    return 0;
}

void
sc_phoneview_ui_pump_events(struct sc_phoneview_ui *ui) {
    (void) ui;
}

#endif
