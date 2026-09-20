#ifdef __linux__
#include "phoneview_ui.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <gtk/gtk.h>
#include <gdk/gdkx.h>

#include <SDL3/SDL.h>

#include "util/log.h"

#define PHONEVIEW_UI_TITLEBAR_HEIGHT 42
#define PHONEVIEW_UI_TOOLBAR_HEIGHT 50
#define PHONEVIEW_UI_MIN_VIDEO_WIDTH 240
#define PHONEVIEW_UI_MIN_VIDEO_HEIGHT 320

struct sc_phoneview_ui {
    GtkWidget *window;

    GtkWidget *headerbar;
    GtkWidget *title_icon;
    GtkWidget *title_label;
    GtkWidget *title_subtitle;
    GtkWidget *minimize_button;
    GtkWidget *maximize_button;
    GtkWidget *close_button;

    GtkWidget *toolbar;
    GtkWidget *edit_button;
    GtkWidget *add_button;
    GtkWidget *save_button;
    GtkWidget *done_button;
    GtkWidget *separator;
    GtkWidget *status_label;

    GtkWidget *video_area;
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

static bool
phoneview_ui_asset_path(const char *filename, char *out, size_t out_size) {
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

static GtkWidget *
phoneview_make_icon_button(const char *icon_name, const char *name) {
    GtkWidget *button =
        gtk_button_new_from_icon_name(icon_name, GTK_ICON_SIZE_BUTTON);
    gtk_widget_set_name(button, name);
    gtk_widget_set_can_focus(button, FALSE);
    gtk_widget_set_valign(button, GTK_ALIGN_CENTER);
    return button;
}

static GtkWidget *
phoneview_make_toolbar_button(const char *label,
                              const char *icon_name,
                              const char *name) {
    GtkWidget *button = gtk_button_new_with_label(label);
    GtkWidget *image =
        gtk_image_new_from_icon_name(icon_name, GTK_ICON_SIZE_BUTTON);
    gtk_button_set_image(GTK_BUTTON(button), image);
    gtk_button_set_always_show_image(GTK_BUTTON(button), TRUE);
    gtk_widget_set_name(button, name);
    gtk_widget_set_can_focus(button, FALSE);
    gtk_widget_set_valign(button, GTK_ALIGN_CENTER);
    return button;
}

static void
phoneview_ui_update_maximize_icon(struct sc_phoneview_ui *ui) {
    if (!ui || !ui->maximize_button) {
        return;
    }

    bool maximized = gtk_window_is_maximized(GTK_WINDOW(ui->window));
    const char *icon =
        maximized ? "view-restore-symbolic" : "view-maximize-symbolic";
    GtkWidget *image =
        gtk_image_new_from_icon_name(icon, GTK_ICON_SIZE_BUTTON);
    gtk_button_set_image(GTK_BUTTON(ui->maximize_button), image);
    gtk_button_set_always_show_image(GTK_BUTTON(ui->maximize_button), TRUE);
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

    phoneview_ui_update_maximize_icon(ui);
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

    phoneview_ui_update_maximize_icon(userdata);
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

static void
phoneview_ui_sync_video_size(struct sc_phoneview_ui *ui) {
    if (!ui || !ui->video_window || !ui->video_area) {
        return;
    }

    int width = gtk_widget_get_allocated_width(ui->video_area);
    int height = gtk_widget_get_allocated_height(ui->video_area);
    if (width <= 0 || height <= 0) {
        return;
    }

    int current_width = 0;
    int current_height = 0;
    SDL_GetWindowSize(ui->video_window, &current_width, &current_height);
    if (current_width != width || current_height != height) {
        SDL_SetWindowSize(ui->video_window, width, height);
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
phoneview_ui_update_visibility(struct sc_phoneview_ui *ui) {
    if (!ui) {
        return;
    }

    gtk_widget_set_visible(ui->edit_button, !ui->edit_mode);
    gtk_widget_set_visible(ui->add_button, ui->edit_mode);
    gtk_widget_set_visible(ui->save_button, ui->edit_mode);
    gtk_widget_set_visible(ui->done_button, ui->edit_mode);
    gtk_widget_set_visible(ui->separator, ui->edit_mode);
    gtk_widget_set_visible(ui->status_label, ui->edit_mode);

    if (!ui->edit_mode) {
        gtk_label_set_text(GTK_LABEL(ui->status_label), "");
    } else if (ui->capture_mode) {
        gtk_label_set_text(
            GTK_LABEL(ui->status_label),
            "Waiting for input  •  Esc to cancel"
        );
    } else {
        gtk_label_set_text(
            GTK_LABEL(ui->status_label),
            "Control mapping"
        );
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

    if (ui->title_icon) {
        gtk_image_set_from_file(GTK_IMAGE(ui->title_icon), icon_path);
        gtk_image_set_pixel_size(GTK_IMAGE(ui->title_icon), 26);
    }
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
    gtk_window_set_default_size(
        GTK_WINDOW(ui->window),
        video_width,
        video_height + PHONEVIEW_UI_TOOLBAR_HEIGHT
    );
    gtk_window_set_geometry_hints(
        GTK_WINDOW(ui->window),
        NULL,
        &(GdkGeometry) {
            .min_width = PHONEVIEW_UI_MIN_VIDEO_WIDTH,
            .min_height = PHONEVIEW_UI_MIN_VIDEO_HEIGHT
                           + PHONEVIEW_UI_TOOLBAR_HEIGHT,
        },
        GDK_HINT_MIN_SIZE
    );

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

    /*
     * Custom native headerbar:
     * it replaces the normal desktop title bar while GTK still keeps
     * native moving/resizing behavior for the top-level window.
     */
    ui->headerbar = gtk_header_bar_new();
    gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(ui->headerbar), FALSE);
    gtk_header_bar_set_title_widget(GTK_HEADER_BAR(ui->headerbar), NULL);
    gtk_widget_set_name(ui->headerbar, "phoneview-titlebar");
    gtk_widget_set_size_request(ui->headerbar, -1,
                                PHONEVIEW_UI_TITLEBAR_HEIGHT);

    GtkWidget *title_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_widget_set_valign(title_box, GTK_ALIGN_CENTER);

    ui->title_icon = gtk_image_new();
    gtk_widget_set_valign(ui->title_icon, GTK_ALIGN_CENTER);

    GtkWidget *title_text_box =
        gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_widget_set_valign(title_text_box, GTK_ALIGN_CENTER);

    ui->title_label = gtk_label_new("PhoneView");
    ui->title_subtitle = gtk_label_new(title ? title : "Android Viewer");

    gtk_widget_set_name(ui->title_label, "phoneview-title");
    gtk_widget_set_name(ui->title_subtitle, "phoneview-subtitle");
    gtk_label_set_xalign(GTK_LABEL(ui->title_label), 0.f);
    gtk_label_set_xalign(GTK_LABEL(ui->title_subtitle), 0.f);

    gtk_box_pack_start(GTK_BOX(title_text_box),
                       ui->title_label,
                       FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(title_text_box),
                       ui->title_subtitle,
                       FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(title_box),
                       ui->title_icon,
                       FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(title_box),
                       title_text_box,
                       FALSE, FALSE, 0);

    gtk_header_bar_set_custom_title(GTK_HEADER_BAR(ui->headerbar),
                                    title_box);

    ui->minimize_button =
        phoneview_make_icon_button("window-minimize-symbolic",
                                   "phoneview-window-minimize");
    ui->maximize_button =
        phoneview_make_icon_button("view-maximize-symbolic",
                                   "phoneview-window-maximize");
    ui->close_button =
        phoneview_make_icon_button("window-close-symbolic",
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

    ui->toolbar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_widget_set_name(ui->toolbar, "phoneview-toolbar");
    gtk_widget_set_size_request(ui->toolbar, -1,
                                PHONEVIEW_UI_TOOLBAR_HEIGHT);
    gtk_box_pack_start(GTK_BOX(root), ui->toolbar,
                       FALSE, FALSE, 0);

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
    ui->separator = gtk_separator_new(GTK_ORIENTATION_VERTICAL);
    ui->status_label = gtk_label_new("");

    GtkWidget *toolbar_widgets[] = {
        ui->edit_button,
        ui->add_button,
        ui->save_button,
        ui->separator,
        ui->done_button,
    };

    for (size_t i = 0;
         i < sizeof(toolbar_widgets) / sizeof(toolbar_widgets[0]);
         ++i) {
        GtkWidget *widget = toolbar_widgets[i];
        gtk_widget_set_margin_start(widget, 5);
        gtk_widget_set_margin_end(widget, 1);
        gtk_widget_set_valign(widget, GTK_ALIGN_CENTER);
        gtk_box_pack_start(GTK_BOX(ui->toolbar),
                           widget,
                           FALSE, FALSE, 0);
    }

    gtk_widget_set_margin_start(ui->status_label, 12);
    gtk_widget_set_margin_end(ui->status_label, 12);
    gtk_widget_set_valign(ui->status_label, GTK_ALIGN_CENTER);
    gtk_widget_set_halign(ui->status_label, GTK_ALIGN_END);
    gtk_box_pack_end(GTK_BOX(ui->toolbar),
                     ui->status_label,
                     FALSE, FALSE, 0);

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
        " background-color: #0e1218;"
        " border-bottom: 1px solid #232a34;"
        " padding: 0 7px;"
        "}"
        "#phoneview-title {"
        " color: #f2f5f8;"
        " font-weight: 700;"
        " font-size: 13px;"
        "}"
        "#phoneview-subtitle {"
        " color: #7f8b9a;"
        " font-size: 10px;"
        "}"
        "#phoneview-titlebar button {"
        " min-width: 38px;"
        " min-height: 30px;"
        " padding: 0;"
        " margin: 0 1px;"
        " border: none;"
        " border-radius: 6px;"
        " background: transparent;"
        " color: #aeb7c3;"
        " box-shadow: none;"
        "}"
        "#phoneview-titlebar button:hover {"
        " background: #252c35;"
        " color: #ffffff;"
        "}"
        "#phoneview-titlebar #phoneview-window-close:hover {"
        " background: #c94351;"
        " color: #ffffff;"
        "}"
        "#phoneview-toolbar {"
        " background: #171c23;"
        " border-bottom: 1px solid #252c35;"
        " padding: 4px 5px;"
        "}"
        "#phoneview-toolbar button {"
        " color: #dfe5ec;"
        " background: transparent;"
        " border: 1px solid transparent;"
        " border-radius: 7px;"
        " padding: 6px 11px;"
        " font-size: 11px;"
        " box-shadow: none;"
        "}"
        "#phoneview-toolbar button:hover {"
        " background: #252d37;"
        " border-color: #323b47;"
        "}"
        "#phoneview-toolbar button:active {"
        " background: #2f3945;"
        "}"
        "#phoneview-toolbar #phoneview-add-button {"
        " color: #ffffff;"
        " background: #2d6cdf;"
        " border-color: #4682ee;"
        "}"
        "#phoneview-toolbar #phoneview-add-button:hover {"
        " background: #3a79ea;"
        "}"
        "#phoneview-toolbar #phoneview-save-button {"
        " color: #b9c6d5;"
        "}"
        "#phoneview-toolbar #phoneview-done-button {"
        " color: #a6e3bc;"
        "}"
        "#phoneview-toolbar separator {"
        " margin: 7px 6px;"
        "}"
        "#phoneview-toolbar #phoneview-status {"
        " color: #8693a3;"
        " font-size: 10px;"
        " padding-left: 10px;"
        "}";
    gtk_css_provider_load_from_data(provider, css, -1, NULL);
    GdkScreen *style_screen = gtk_widget_get_screen(ui->window);
    gtk_style_context_add_provider_for_screen(
        style_screen,
        GTK_STYLE_PROVIDER(provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(provider);

    ui->video_area = gtk_drawing_area_new();
    gtk_widget_set_name(ui->video_area, "phoneview-video");
    gtk_widget_set_hexpand(ui->video_area, TRUE);
    gtk_widget_set_vexpand(ui->video_area, TRUE);
    gtk_widget_set_can_focus(ui->video_area, TRUE);
    gtk_widget_set_size_request(
        ui->video_area,
        PHONEVIEW_UI_MIN_VIDEO_WIDTH,
        PHONEVIEW_UI_MIN_VIDEO_HEIGHT
    );
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

    GdkWindow *gdk_video_window = gtk_widget_get_window(ui->video_area);
    if (!gdk_video_window) {
        LOGE("PhoneView UI: failed to realize the video surface");
        sc_phoneview_ui_destroy(ui);
        return NULL;
    }

    Window xid = gdk_x11_window_get_xid(gdk_video_window);

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
    phoneview_ui_update_maximize_icon(ui);
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

    gtk_window_resize(
        GTK_WINDOW(ui->window),
        video_width,
        video_height + PHONEVIEW_UI_TOOLBAR_HEIGHT
    );

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
