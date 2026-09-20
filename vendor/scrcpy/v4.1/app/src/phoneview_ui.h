#ifndef SC_PHONEVIEW_UI_H
#define SC_PHONEVIEW_UI_H

#include <stdbool.h>
#include <stdint.h>
#include <SDL3/SDL_video.h>

enum sc_phoneview_ui_action {
    SC_PHONEVIEW_UI_ACTION_EDIT,
    SC_PHONEVIEW_UI_ACTION_ADD,
    SC_PHONEVIEW_UI_ACTION_SAVE,
    SC_PHONEVIEW_UI_ACTION_DONE,
    SC_PHONEVIEW_UI_ACTION_CLOSE,
};

typedef void (*sc_phoneview_ui_action_cb)(
    enum sc_phoneview_ui_action action,
    void *userdata
);

struct sc_phoneview_ui;

struct sc_phoneview_ui *
sc_phoneview_ui_create(const char *title,
                       int video_width,
                       int video_height,
                       bool always_on_top,
                       bool decorated,
                       sc_phoneview_ui_action_cb action_cb,
                       void *userdata);

void
sc_phoneview_ui_destroy(struct sc_phoneview_ui *ui);

SDL_Window *
sc_phoneview_ui_get_video_window(struct sc_phoneview_ui *ui);

void
sc_phoneview_ui_show(struct sc_phoneview_ui *ui);

void
sc_phoneview_ui_hide(struct sc_phoneview_ui *ui);

void
sc_phoneview_ui_set_window_size(struct sc_phoneview_ui *ui,
                                int video_width,
                                int video_height);

void
sc_phoneview_ui_set_window_position(struct sc_phoneview_ui *ui,
                                    int x,
                                    int y);

void
sc_phoneview_ui_set_fullscreen(struct sc_phoneview_ui *ui,
                               bool fullscreen);

void
sc_phoneview_ui_set_edit_mode(struct sc_phoneview_ui *ui,
                              bool edit_mode);

void
sc_phoneview_ui_set_capture_mode(struct sc_phoneview_ui *ui,
                                 bool capture_mode);

bool
sc_phoneview_ui_is_edit_mode(struct sc_phoneview_ui *ui);

int
sc_phoneview_ui_get_toolbar_height(struct sc_phoneview_ui *ui);

void
sc_phoneview_ui_pump_events(struct sc_phoneview_ui *ui);

#endif
