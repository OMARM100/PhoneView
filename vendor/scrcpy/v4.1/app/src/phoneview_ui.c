#ifdef __linux__
#include "phoneview_ui.h"

#include <stdlib.h>
#include <gtk/gtk.h>
#include <gdk/gdkx.h>

#include <SDL3/SDL.h>

#include "util/log.h"

#define PHONEVIEW_UI_TOOLBAR_HEIGHT 48

struct sc_phoneview_ui {
    GtkWidget *window;
    GtkWidget *toolbar;
    GtkToolItem *edit_button;
    GtkToolItem *add_button;
    GtkToolItem *done_button;
    GtkToolItem *separator;
    GtkToolItem *status_item;
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

static void
phoneview_ui_on_edit(GtkToolButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_EDIT);
}

static void
phoneview_ui_on_add(GtkToolButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_ADD);
}

static void
phoneview_ui_on_done(GtkToolButton *button, gpointer userdata) {
    (void) button;
    phoneview_ui_emit(userdata, SC_PHONEVIEW_UI_ACTION_DONE);
}

static gboolean
phoneview_ui_on_delete_event(GtkWidget *widget,
                             GdkEvent *event,
                             gpointer userdata) {
    (void) widget;
    (void) event;

    struct sc_phoneview_ui *ui = userdata;
    phoneview_ui_emit(ui, SC_PHONEVIEW_UI_ACTION_CLOSE);
    return TRUE;
}

static void
phoneview_ui_update_visibility(struct sc_phoneview_ui *ui) {
    if (!ui) {
        return;
    }

    gtk_widget_set_visible(GTK_WIDGET(ui->edit_button), !ui->edit_mode);
    gtk_widget_set_visible(GTK_WIDGET(ui->add_button), ui->edit_mode);
    gtk_widget_set_visible(GTK_WIDGET(ui->done_button), ui->edit_mode);
    gtk_widget_set_visible(GTK_WIDGET(ui->separator), ui->edit_mode);
    gtk_widget_set_visible(GTK_WIDGET(ui->status_item),
                           ui->edit_mode && ui->capture_mode);

    if (!ui->edit_mode) {
        gtk_label_set_text(GTK_LABEL(ui->status_label), "");
    } else if (ui->capture_mode) {
        gtk_label_set_text(GTK_LABEL(ui->status_label),
                           "Press a key, mouse button, or wheel...");
    } else {
        gtk_label_set_text(GTK_LABEL(ui->status_label),
                           "Edit mode");
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
    gtk_window_set_title(GTK_WINDOW(ui->window), title);
    gtk_window_set_decorated(GTK_WINDOW(ui->window), decorated);
    gtk_window_set_resizable(GTK_WINDOW(ui->window), TRUE);
    gtk_window_set_default_size(GTK_WINDOW(ui->window),
                                video_width,
                                video_height + PHONEVIEW_UI_TOOLBAR_HEIGHT);
    if (always_on_top) {
        gtk_window_set_keep_above(GTK_WINDOW(ui->window), TRUE);
    }

    g_signal_connect(ui->window, "delete-event",
                     G_CALLBACK(phoneview_ui_on_delete_event), ui);

    GtkWidget *root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_container_add(GTK_CONTAINER(ui->window), root);

    ui->toolbar = gtk_toolbar_new();
    gtk_toolbar_set_style(GTK_TOOLBAR(ui->toolbar), GTK_TOOLBAR_TEXT);
    gtk_toolbar_set_icon_size(GTK_TOOLBAR(ui->toolbar), GTK_ICON_SIZE_BUTTON);
    gtk_widget_set_size_request(ui->toolbar, -1,
                                PHONEVIEW_UI_TOOLBAR_HEIGHT);
    gtk_box_pack_start(GTK_BOX(root), ui->toolbar,
                       FALSE, FALSE, 0);

    ui->edit_button =
        gtk_tool_button_new(NULL, "Edit");
    gtk_tool_item_set_is_important(ui->edit_button, TRUE);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), ui->edit_button, -1);
    g_signal_connect(ui->edit_button, "clicked",
                     G_CALLBACK(phoneview_ui_on_edit), ui);

    ui->add_button =
        gtk_tool_button_new(NULL, "Add Button");
    gtk_tool_item_set_is_important(ui->add_button, TRUE);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), ui->add_button, -1);
    g_signal_connect(ui->add_button, "clicked",
                     G_CALLBACK(phoneview_ui_on_add), ui);

    ui->separator = gtk_separator_tool_item_new();
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), ui->separator, -1);

    ui->done_button =
        gtk_tool_button_new(NULL, "Done");
    gtk_tool_item_set_is_important(ui->done_button, TRUE);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), ui->done_button, -1);
    g_signal_connect(ui->done_button, "clicked",
                     G_CALLBACK(phoneview_ui_on_done), ui);

    ui->status_item = gtk_tool_item_new();
    gtk_tool_item_set_expand(ui->status_item, TRUE);
    ui->status_label = gtk_label_new("");
    gtk_widget_set_halign(ui->status_label, GTK_ALIGN_END);
    gtk_widget_set_margin_end(ui->status_label, 12);
    gtk_container_add(GTK_CONTAINER(ui->status_item), ui->status_label);
    gtk_toolbar_insert(GTK_TOOLBAR(ui->toolbar), ui->status_item, -1);

    ui->video_area = gtk_drawing_area_new();
    gtk_widget_set_hexpand(ui->video_area, TRUE);
    gtk_widget_set_vexpand(ui->video_area, TRUE);
    gtk_widget_set_can_focus(ui->video_area, TRUE);
    gtk_box_pack_start(GTK_BOX(root), ui->video_area,
                       TRUE, TRUE, 0);

    gtk_widget_show(ui->toolbar);
    gtk_widget_show(GTK_WIDGET(ui->edit_button));
    gtk_widget_show(ui->video_area);
    gtk_widget_show(root);
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

    gtk_widget_show(ui->window);
    gtk_window_present(GTK_WINDOW(ui->window));
    while (gtk_events_pending()) {
        gtk_main_iteration_do(FALSE);
    }
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

    gtk_window_resize(GTK_WINDOW(ui->window),
                      video_width,
                      video_height + PHONEVIEW_UI_TOOLBAR_HEIGHT);
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
