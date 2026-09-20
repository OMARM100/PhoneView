#ifdef __linux__
#include "phoneview_ui.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <gtk/gtk.h>
#include <gdk/gdkx.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>

#include <SDL3/SDL.h>

#include "util/log.h"

#define PHONEVIEW_UI_TITLEBAR_HEIGHT 38
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
    SDL_Window *video_window;

    sc_phoneview_ui_action_cb action_cb;
    void *userdata;
    bool edit_mode;
    bool capture_mode;
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
phoneview_ui_on_add(GtkButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_ADD);
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
phoneview_ui_asset_path(const char *filename,
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

    int written = snprintf(
        out,
        out_size,
        "%s/share/icons/hicolor/scalable/apps/%s",
        executable,
        filename
    );

    return written > 0 && (size_t) written < out_size;
}

static void
phoneview_ui_set_skip_taskbar(Window xid) {
    GdkDisplay *gdk_display = gdk_display_get_default();
    if (!gdk_display || !GDK_IS_X11_DISPLAY(gdk_display)) {
        return;
    }

    Display *display = gdk_x11_display_get_xdisplay(gdk_display);
    Atom wm_state = XInternAtom(display, "_NET_WM_STATE", False);
    Atom skip_taskbar = XInternAtom(display,
                                    "_NET_WM_STATE_SKIP_TASKBAR",
                                    False);

    XChangeProperty(display,
                    xid,
                    wm_state,
                    XA_ATOM,
                    32,
                    PropModeAppend,
                    (unsigned char *) &skip_taskbar,
                    1);
    XFlush(display);
}

static void
phoneview_ui_sync_video_size(struct sc_phoneview_ui *ui) {
    if (!ui || !ui->video_gdk_window) {
        return;
    }

    int width = gtk_widget_get_allocated_width(ui->video_area);
    int height = gtk_widget_get_allocated_height(ui->video_area);

    if (width <= 0 || height <= 0) {
        return;
    }

    GdkWindow *window = ui->video_gdk_window;
    gint current_width = 0;
    gint current_height = 0;

    gdk_window_get_geometry(window,
                            NULL,
                            NULL,
                            &current_width,
                            &current_height);

    if (current_width != width || current_height != height) {
        gdk_window_move_resize(window, 0, 0, width, height);
    }

    if (ui->video_window) {
        int sdl_width = 0;
        int sdl_height = 0;
        SDL_GetWindowSize(ui->video_window, &sdl_width, &sdl_height);

        if (sdl_width != width || sdl_height != height) {
            (void) SDL_SetWindowSize(ui->video_window, width, height);
        }
    }
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

    GdkScreen *screen = gtk_widget_get_screen(ui->window);
    if (!screen) {
        return;
    }

    GdkRectangle workarea = {0};
    gint monitor = gdk_screen_get_primary_monitor(screen);
    gdk_screen_get_monitor_workarea(screen, monitor, &workarea);

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

    gtk_widget_set_visible(ui->edit_button, !ui->edit_mode);
    gtk_widget_set_visible(ui->add_button, ui->edit_mode);
    gtk_widget_set_visible(ui->save_button, ui->edit_mode);
    gtk_widget_set_visible(ui->done_button, ui->edit_mode);
    gtk_widget_set_visible(ui->status_label, ui->edit_mode);

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
phoneview_ui_apply_icon(struct sc_phoneview_ui *ui) {
    char icon_path[PATH_MAX];
    if (!phoneview_ui_asset_path("phoneview.svg",
                                 icon_path,
                                 sizeof(icon_path))) {
        return;
    }

    gtk_window_set_icon_from_file(GTK_WINDOW(ui->window),
                                  icon_path,
                                  NULL);

    gtk_image_set_from_file(GTK_IMAGE(ui->title_icon), icon_path);
    gtk_image_set_pixel_size(GTK_IMAGE(ui->title_icon), 22);
    gtk_widget_set_size_request(ui->title_icon, 22, 22);
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
    (void) title;

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
    ui->title_project = gtk_label_new("Android Viewer");

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
    GtkToolItem *add_item = gtk_tool_item_new();
    GtkToolItem *save_item = gtk_tool_item_new();
    GtkToolItem *done_item = gtk_tool_item_new();

    ui->edit_button =
        phoneview_make_toolbar_button("Edit",
                                       "document-edit-symbolic",
                                       "phoneview-edit-button");
    ui->add_button =
        phoneview_make_toolbar_button("Add Button",
                                       "list-add-symbolic",
                                       "phoneview-add-button");
    ui->save_button =
        phoneview_make_toolbar_button("Save",
                                       "document-save-symbolic",
                                       "phoneview-save-button");
    ui->done_button =
        phoneview_make_toolbar_button("Done",
                                       "emblem-ok-symbolic",
                                       "phoneview-done-button");

    gtk_container_add(GTK_CONTAINER(edit_item), ui->edit_button);
    gtk_container_add(GTK_CONTAINER(add_item), ui->add_button);
    gtk_container_add(GTK_CONTAINER(save_item), ui->save_button);
    gtk_container_add(GTK_CONTAINER(done_item), ui->done_button);

    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), edit_item, -1);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), add_item, -1);
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

    GtkCssProvider *provider = gtk_css_provider_new();
    const gchar *css =
        "#phoneview-titlebar {"
        " background: #0f141b;"
        " border: none;"
        " box-shadow: none;"
        " min-height: 38px;"
        " padding: 0 5px;"
        "}"
        "#phoneview-title {"
        " color: #eef3f8;"
        " font-weight: 700;"
        " font-size: 12px;"
        "}"
        "#phoneview-project {"
        " color: #7e8a99;"
        " font-size: 10px;"
        " margin-left: 2px;"
        "}"
        "#phoneview-titlebar button {"
        " color: #aeb8c5;"
        " background: transparent;"
        " border: none;"
        " border-radius: 4px;"
        " font-size: 15px;"
        " padding: 0;"
        " margin: 0;"
        "}"
        "#phoneview-titlebar #phoneview-window-minimize:hover,"
        "#phoneview-titlebar #phoneview-window-maximize:hover {"
        " background: #29313c;"
        " color: #ffffff;"
        "}"
        "#phoneview-titlebar #phoneview-window-close:hover {"
        " background: #c94755;"
        " color: #ffffff;"
        "}"
        "#phoneview-toolbar {"
        " background: #171d25;"
        " border: none;"
        " border-bottom: 1px solid #252e39;"
        " padding: 2px 5px;"
        "}"
        "#phoneview-toolbar toolitem {"
        " padding: 0;"
        "}"
        "#phoneview-toolbar button {"
        " color: #cbd5df;"
        " background: transparent;"
        " border: 1px solid transparent;"
        " border-radius: 5px;"
        " padding: 5px 9px;"
        " margin: 2px 1px;"
        " box-shadow: none;"
        "}"
        "#phoneview-toolbar button:hover {"
        " background: #27313d;"
        " border-color: #344150;"
        "}"
        "#phoneview-toolbar #phoneview-add-button {"
        " color: #ffffff;"
        " background: #2768d9;"
        " border-color: #3f7ae7;"
        "}"
        "#phoneview-toolbar #phoneview-add-button:hover {"
        " background: #3478eb;"
        "}"
        "#phoneview-toolbar #phoneview-done-button {"
        " color: #a6e3bb;"
        "}"
        "#phoneview-toolbar #phoneview-status {"
        " color: #7f8b99;"
        " font-size: 10px;"
        " padding: 0 10px;"
        "}"
        "#phoneview-video {"
        " background: #05070a;"
        "}";
    gtk_css_provider_load_from_data(provider, css, -1, NULL);
    gtk_style_context_add_provider_for_screen(
        gtk_widget_get_screen(ui->window),
        GTK_STYLE_PROVIDER(provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(provider);

    ui->video_area = gtk_drawing_area_new();
    gtk_widget_set_name(ui->video_area, "phoneview-video");
    gtk_widget_set_hexpand(ui->video_area, TRUE);
    gtk_widget_set_vexpand(ui->video_area, TRUE);
    gtk_widget_set_can_focus(ui->video_area, TRUE);
    gtk_widget_set_size_request(ui->video_area,
                                PHONEVIEW_UI_MIN_VIDEO_WIDTH,
                                PHONEVIEW_UI_MIN_VIDEO_HEIGHT);

    gtk_box_pack_start(GTK_BOX(root), ui->video_area,
                       TRUE, TRUE, 0);

    g_signal_connect(ui->video_area,
                     "size-allocate",
                     G_CALLBACK(phoneview_ui_on_video_allocate),
                     ui);

    phoneview_ui_apply_icon(ui);

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

    Window xid = gdk_x11_window_get_xid(ui->video_gdk_window);
    phoneview_ui_set_skip_taskbar(xid);

    SDL_PropertiesID props = SDL_CreateProperties();
    if (!props) {
        LOGE("PhoneView UI: SDL_CreateProperties() failed: %s",
             SDL_GetError());
        sc_phoneview_ui_destroy(ui);
        return NULL;
    }

    SDL_SetNumberProperty(props,
                          SDL_PROP_WINDOW_CREATE_X11_WINDOW_NUMBER,
                          (Sint64) xid);

    ui->video_window = SDL_CreateWindowWithProperties(props);
    SDL_DestroyProperties(props);

    if (!ui->video_window) {
        LOGE("PhoneView UI: SDL_CreateWindowWithProperties() failed: %s",
             SDL_GetError());
        sc_phoneview_ui_destroy(ui);
        return NULL;
    }

    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }

    phoneview_ui_sync_video_size(ui);
    phoneview_ui_update_maximize_button(ui);
    sc_phoneview_ui_set_edit_mode(ui, false);
    sc_phoneview_ui_set_capture_mode(ui, false);

    return ui;
}

void
sc_phoneview_ui_destroy(struct sc_phoneview_ui *ui) {
    if (!ui) {
        return;
    }

    if (ui->video_window) {
        SDL_DestroyWindow(ui->video_window);
        ui->video_window = NULL;
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

    if (capture_mode && ui->video_area) {
        gtk_widget_grab_focus(ui->video_area);
    }
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
