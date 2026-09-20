/* PhoneView modification: based on Genymobile/scrcpy v4.1.
 * Adds the PhoneView in-window mapping editor and key/mouse/wheel mapping.
 */
#include "screen.h"

#include <assert.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef _WIN32
# include <sys/stat.h>
#endif
#include <SDL3/SDL.h>

#include "events.h"
#include "icon.h"
#include "options.h"
#include "util/log.h"
#include "util/sdl.h"

#define DISPLAY_MARGINS 96

#define DOWNCAST(SINK) container_of(SINK, struct sc_screen, frame_sink)

#define PHONEVIEW_MAX_CONTROLS 64
#define PHONEVIEW_CONTROL_W 76.f
#define PHONEVIEW_CONTROL_H 42.f

static void
phoneview_config_path(char *path, size_t size) {
    const char *home = getenv("HOME");
    if (!home) {
        path[0] = '\0';
        return;
    }
    snprintf(path, size, "%s/.config/PhoneView/controls.json", home);
}

static bool
phoneview_json_string(const char *begin, const char *end, const char *key,
                      char *out, size_t out_size) {
    char pattern[96];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);

    const char *p = begin;
    while ((p = strstr(p, pattern))) {
        if (p >= end) {
            return false;
        }
        const char *q = p + strlen(pattern);
        while (q < end && isspace((unsigned char) *q)) q++;
        if (q >= end || *q != ':') {
            p += strlen(pattern);
            continue;
        }
        q++;
        while (q < end && isspace((unsigned char) *q)) q++;
        if (q >= end || *q != '"') {
            return false;
        }
        q++;
        size_t i = 0;
        while (q < end && *q != '"' && i + 1 < out_size) {
            if (*q == '\\' && q + 1 < end) {
                q++;
            }
            out[i++] = *q++;
        }
        if (q >= end || *q != '"') {
            return false;
        }
        out[i] = '\0';
        return true;
    }
    return false;
}

static bool
phoneview_json_float(const char *begin, const char *end, const char *key,
                     float *out) {
    char pattern[96];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);

    const char *p = strstr(begin, pattern);
    if (!p || p >= end) {
        return false;
    }

    p += strlen(pattern);
    while (p < end && isspace((unsigned char) *p)) p++;
    if (p >= end || *p != ':') {
        return false;
    }
    p++;
    while (p < end && isspace((unsigned char) *p)) p++;
    if (p >= end) {
        return false;
    }

    char *number_end = NULL;
    float value = strtof(p, &number_end);
    if (number_end == p || number_end > end) {
        return false;
    }

    *out = value;
    return true;
}

static void
phoneview_load_controls(struct sc_screen *screen) {
    screen->phoneview.count = 0;

    char path[1024];
    phoneview_config_path(path, sizeof(path));
    if (!path[0]) {
        return;
    }

    FILE *file = fopen(path, "rb");
    if (!file) {
        return;
    }

    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return;
    }

    long length = ftell(file);
    if (length <= 0 || length > 1024 * 1024) {
        fclose(file);
        return;
    }

    rewind(file);

    char *data = malloc((size_t) length + 1);
    if (!data) {
        fclose(file);
        return;
    }

    size_t read = fread(data, 1, (size_t) length, file);
    fclose(file);
    data[read] = '\0';

    const char *cursor = data;
    while (screen->phoneview.count < PHONEVIEW_MAX_CONTROLS) {
        const char *object = strchr(cursor, '{');
        if (!object) {
            break;
        }

        const char *end = strchr(object, '}');
        if (!end) {
            break;
        }

        struct sc_phoneview_control control = {0};
        if (!phoneview_json_string(object, end, "label",
                                   control.label, sizeof(control.label))) {
            cursor = end + 1;
            continue;
        }

        phoneview_json_string(object, end, "key",
                              control.key, sizeof(control.key));
        phoneview_json_string(object, end, "type",
                              control.type, sizeof(control.type));
        phoneview_json_string(object, end, "mouse_button",
                              control.mouse_button,
                              sizeof(control.mouse_button));

        if (!phoneview_json_float(object, end, "x", &control.x)) {
            control.x = 0.45f;
        }
        if (!phoneview_json_float(object, end, "y", &control.y)) {
            control.y = 0.45f;
        }

        control.x = SDL_clamp(control.x, 0.f, 1.f);
        control.y = SDL_clamp(control.y, 0.f, 1.f);

        screen->phoneview.controls[screen->phoneview.count++] = control;
        cursor = end + 1;
    }

    free(data);
}

static void
phoneview_ensure_config_directory(void) {
    const char *home = getenv("HOME");
    if (!home) {
        return;
    }

    char base[1024];
    snprintf(base, sizeof(base), "%s/.config", home);
    (void) mkdir(base, 0755);

    snprintf(base, sizeof(base), "%s/.config/PhoneView", home);
    (void) mkdir(base, 0755);
}

static void
phoneview_save_controls(struct sc_screen *screen) {
    phoneview_ensure_config_directory();

    char path[1024];
    phoneview_config_path(path, sizeof(path));
    if (!path[0]) {
        return;
    }

    FILE *file = fopen(path, "wb");
    if (!file) {
        return;
    }

    fprintf(file, "[\n");
    for (size_t i = 0; i < screen->phoneview.count; ++i) {
        const struct sc_phoneview_control *control =
            &screen->phoneview.controls[i];

        fprintf(
            file,
            "  {\"label\":\"%s\",\"key\":\"%s\",\"type\":\"%s\","
            "\"x\":%.5f,\"y\":%.5f",
            control->label,
            control->key,
            control->type,
            control->x,
            control->y
        );

        if (control->mouse_button[0]) {
            fprintf(file, ",\"mouse_button\":\"%s\"", control->mouse_button);
        }

        fprintf(file, "}%s\n",
                i + 1 == screen->phoneview.count ? "" : ",");
    }
    fprintf(file, "]\n");

    fclose(file);
}

static bool
phoneview_point_in_rect(float x, float y, float rx, float ry,
                        float rw, float rh) {
    return x >= rx && x < rx + rw && y >= ry && y < ry + rh;
}

static int
phoneview_hit_control(struct sc_screen *screen, float x, float y,
                       float width, float height) {
    for (size_t i = 0; i < screen->phoneview.count; ++i) {
        const struct sc_phoneview_control *control =
            &screen->phoneview.controls[i];

        float bx = control->x * width - PHONEVIEW_CONTROL_W / 2.f;
        float by = control->y * height - PHONEVIEW_CONTROL_H / 2.f;

        if (phoneview_point_in_rect(x, y, bx, by,
                                     PHONEVIEW_CONTROL_W,
                                     PHONEVIEW_CONTROL_H)) {
            return (int) i;
        }
    }
    return -1;
}

static struct sc_phoneview_control *
phoneview_find_keyboard_control(struct sc_screen *screen, const char *label,
                                size_t *index_out) {
    for (size_t i = 0; i < screen->phoneview.count; ++i) {
        struct sc_phoneview_control *control =
            &screen->phoneview.controls[i];
        if (!strcmp(control->type, "keyboard")
                && !strcmp(control->label, label)) {
            if (index_out) {
                *index_out = i;
            }
            return control;
        }
    }
    return NULL;
}

static struct sc_phoneview_control *
phoneview_find_mouse_control(struct sc_screen *screen, const char *button,
                             size_t *index_out) {
    for (size_t i = 0; i < screen->phoneview.count; ++i) {
        struct sc_phoneview_control *control =
            &screen->phoneview.controls[i];
        if (!strcmp(control->type, "mouse")
                && !strcmp(control->mouse_button, button)) {
            if (index_out) {
                *index_out = i;
            }
            return control;
        }
    }
    return NULL;
}

static bool
phoneview_push_touch(struct sc_screen *screen,
                      struct sc_phoneview_control *control,
                      size_t index, enum android_motionevent_action action) {
    if (!screen->controller || !screen->video || !screen->frame_size.width
            || !screen->frame_size.height) {
        return false;
    }

    struct sc_size window_size = sc_sdl_get_window_size(screen->window);
    float wx = control->x * (float) window_size.width;
    float wy = control->y * (float) window_size.height;

    struct sc_point point =
        sc_screen_convert_window_to_frame_coords(screen, (int32_t) wx,
                                                 (int32_t) wy);

    struct sc_control_msg msg = {0};
    msg.type = SC_CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT;
    msg.inject_touch_event.action = action;
    msg.inject_touch_event.action_button = 0;
    msg.inject_touch_event.buttons = 0;
    msg.inject_touch_event.pointer_id = UINT64_C(0x100000) + index;
    msg.inject_touch_event.position.screen_size = screen->frame_size;
    msg.inject_touch_event.position.point = point;
    msg.inject_touch_event.pressure =
        action == AMOTION_EVENT_ACTION_UP ? 0.f : 1.f;

    if (!sc_controller_push_msg(screen->controller, &msg)) {
        return false;
    }

    return true;
}

static bool
phoneview_handle_mapped_keyboard(struct sc_screen *screen,
                                  const SDL_KeyboardEvent *event) {
    const char *name = SDL_GetKeyName(event->key);
    if (!name || !name[0]) {
        return false;
    }

    size_t index = 0;
    struct sc_phoneview_control *control =
        phoneview_find_keyboard_control(screen, name, &index);
    if (!control) {
        return false;
    }

    if (event->type == SDL_EVENT_KEY_DOWN) {
        if (control->active) {
            return true;
        }
        if (phoneview_push_touch(screen, control, index,
                                 AMOTION_EVENT_ACTION_DOWN)) {
            control->active = true;
        }
    } else {
        if (!control->active) {
            return true;
        }
        phoneview_push_touch(screen, control, index,
                             AMOTION_EVENT_ACTION_UP);
        control->active = false;
    }

    return true;
}

static bool
phoneview_handle_mapped_mouse(struct sc_screen *screen,
                               const SDL_MouseButtonEvent *event) {
    const char *name = NULL;
    switch (event->button) {
        case SDL_BUTTON_LEFT:   name = "left"; break;
        case SDL_BUTTON_RIGHT:  name = "right"; break;
        case SDL_BUTTON_MIDDLE: name = "middle"; break;
        case SDL_BUTTON_X1:     name = "x1"; break;
        case SDL_BUTTON_X2:     name = "x2"; break;
        default: return false;
    }

    size_t index = 0;
    struct sc_phoneview_control *control =
        phoneview_find_mouse_control(screen, name, &index);
    if (!control) {
        return false;
    }

    if (event->type == SDL_EVENT_MOUSE_BUTTON_DOWN) {
        if (!control->active) {
            if (phoneview_push_touch(screen, control, index,
                                     AMOTION_EVENT_ACTION_DOWN)) {
                control->active = true;
            }
        }
    } else {
        if (control->active) {
            phoneview_push_touch(screen, control, index,
                                 AMOTION_EVENT_ACTION_UP);
            control->active = false;
        }
    }

    return true;
}

static bool
phoneview_handle_mapped_wheel(struct sc_screen *screen,
                               const SDL_MouseWheelEvent *event) {
    const char *name = NULL;
    if (event->y > 0.f) {
        name = "wheel_up";
    } else if (event->y < 0.f) {
        name = "wheel_down";
    } else if (event->x > 0.f) {
        name = "wheel_right";
    } else if (event->x < 0.f) {
        name = "wheel_left";
    }

    if (!name) {
        return false;
    }

    size_t index = 0;
    struct sc_phoneview_control *control =
        phoneview_find_mouse_control(screen, name, &index);
    if (!control) {
        return false;
    }

    (void) phoneview_push_touch(screen, control, index,
                                AMOTION_EVENT_ACTION_DOWN);
    (void) phoneview_push_touch(screen, control, index,
                                AMOTION_EVENT_ACTION_UP);
    return true;
}

static void
sc_screen_render(struct sc_screen *screen, bool update_content_rect);

static void
phoneview_capture_keyboard(struct sc_screen *screen,
                           const SDL_KeyboardEvent *event) {
    if (screen->phoneview.count >= PHONEVIEW_MAX_CONTROLS) {
        screen->phoneview.capture_mode = false;
        return;
    }

    const char *name = SDL_GetKeyName(event->key);
    if (!name || !name[0]) {
        name = "KEY";
    }

    struct sc_phoneview_control *control =
        &screen->phoneview.controls[screen->phoneview.count++];
    memset(control, 0, sizeof(*control));

    snprintf(control->label, sizeof(control->label), "%s", name);
    snprintf(control->key, sizeof(control->key), "%s", name);
    snprintf(control->type, sizeof(control->type), "keyboard");
    control->x = 0.45f;
    control->y = 0.45f;

    screen->phoneview.capture_mode = false;
    phoneview_save_controls(screen);
    sc_phoneview_ui_set_capture_mode(screen->phoneview.ui, false);
    sc_screen_render(screen, false);
}

static void
phoneview_capture_mouse(struct sc_screen *screen, uint8_t button) {
    if (screen->phoneview.count >= PHONEVIEW_MAX_CONTROLS) {
        screen->phoneview.capture_mode = false;
        return;
    }

    const char *label = "MOUSE";
    const char *mouse_button = "";

    switch (button) {
        case SDL_BUTTON_LEFT:
            label = "LMB";
            mouse_button = "left";
            break;
        case SDL_BUTTON_RIGHT:
            label = "RMB";
            mouse_button = "right";
            break;
        case SDL_BUTTON_MIDDLE:
            label = "MMB";
            mouse_button = "middle";
            break;
        case SDL_BUTTON_X1:
            label = "MOUSE4";
            mouse_button = "x1";
            break;
        case SDL_BUTTON_X2:
            label = "MOUSE5";
            mouse_button = "x2";
            break;
        default:
            return;
    }

    struct sc_phoneview_control *control =
        &screen->phoneview.controls[screen->phoneview.count++];
    memset(control, 0, sizeof(*control));

    snprintf(control->label, sizeof(control->label), "%s", label);
    snprintf(control->key, sizeof(control->key), "%s", label);
    snprintf(control->type, sizeof(control->type), "mouse");
    snprintf(control->mouse_button, sizeof(control->mouse_button), "%s",
             mouse_button);
    control->x = 0.45f;
    control->y = 0.45f;

    screen->phoneview.capture_mode = false;
    phoneview_save_controls(screen);
    sc_phoneview_ui_set_capture_mode(screen->phoneview.ui, false);
    sc_screen_render(screen, false);
}

static void
phoneview_capture_wheel(struct sc_screen *screen, float x, float y) {
    if (screen->phoneview.count >= PHONEVIEW_MAX_CONTROLS) {
        screen->phoneview.capture_mode = false;
        return;
    }

    const char *label = NULL;
    const char *direction = NULL;

    if (y > 0.f) {
        label = "WHEEL_UP";
        direction = "wheel_up";
    } else if (y < 0.f) {
        label = "WHEEL_DOWN";
        direction = "wheel_down";
    } else if (x > 0.f) {
        label = "WHEEL_RIGHT";
        direction = "wheel_right";
    } else if (x < 0.f) {
        label = "WHEEL_LEFT";
        direction = "wheel_left";
    }

    if (!label) {
        return;
    }

    struct sc_phoneview_control *control =
        &screen->phoneview.controls[screen->phoneview.count++];
    memset(control, 0, sizeof(*control));

    snprintf(control->label, sizeof(control->label), "%s", label);
    snprintf(control->key, sizeof(control->key), "%s", label);
    snprintf(control->type, sizeof(control->type), "mouse");
    snprintf(control->mouse_button, sizeof(control->mouse_button), "%s",
             direction);
    control->x = 0.45f;
    control->y = 0.45f;

    screen->phoneview.capture_mode = false;
    phoneview_save_controls(screen);
    sc_phoneview_ui_set_capture_mode(screen->phoneview.ui, false);
    sc_screen_render(screen, false);
}

static void
phoneview_draw_box(SDL_Renderer *renderer, float x, float y, float w, float h,
                   uint8_t r, uint8_t g, uint8_t b, uint8_t a,
                   uint8_t br, uint8_t bg, uint8_t bb, uint8_t ba) {
    SDL_FRect rect = {x, y, w, h};

    SDL_SetRenderDrawColor(renderer, r, g, b, a);
    SDL_RenderFillRect(renderer, &rect);

    SDL_SetRenderDrawColor(renderer, br, bg, bb, ba);
    SDL_RenderRect(renderer, &rect);
}

static void
phoneview_draw_text(SDL_Renderer *renderer, float x, float y,
                    const char *text) {
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    (void) SDL_RenderDebugText(renderer, x, y, text);
}

static void
phoneview_render_controls(struct sc_screen *screen) {
    if (!screen->phoneview.enabled
            || !screen->phoneview.edit_mode
            || !screen->window_shown) {
        return;
    }

    struct sc_size size = sc_sdl_get_window_size(screen->window);
    float width = (float) size.width;
    float height = (float) size.height;

    if (screen->phoneview.capture_mode) {
        SDL_SetRenderDrawBlendMode(screen->renderer, SDL_BLENDMODE_BLEND);
        SDL_SetRenderDrawColor(screen->renderer, 0, 0, 0, 82);

        SDL_FRect overlay = {
            .x = 0.f,
            .y = 0.f,
            .w = width,
            .h = height,
        };
        SDL_RenderFillRect(screen->renderer, &overlay);
    }

    for (size_t i = 0; i < screen->phoneview.count; ++i) {
        const struct sc_phoneview_control *control =
            &screen->phoneview.controls[i];

        float bx = control->x * width - PHONEVIEW_CONTROL_W / 2.f;
        float by = control->y * height - PHONEVIEW_CONTROL_H / 2.f;

        bx = SDL_clamp(bx, 0.f, MAX(0.f, width - PHONEVIEW_CONTROL_W));
        by = SDL_clamp(by, 0.f, MAX(0.f, height - PHONEVIEW_CONTROL_H));

        phoneview_draw_box(screen->renderer,
                           bx, by,
                           PHONEVIEW_CONTROL_W, PHONEVIEW_CONTROL_H,
                           32, 115, 229, 220,
                           255, 255, 255, 210);
        phoneview_draw_text(screen->renderer, bx + 8.f, by + 17.f,
                            control->label);
    }
}

static void
phoneview_ui_action_cb(enum sc_phoneview_ui_action action, void *userdata) {
    struct sc_screen *screen = userdata;
    if (!screen || !screen->phoneview.enabled) {
        return;
    }

    switch (action) {
        case SC_PHONEVIEW_UI_ACTION_EDIT:
            phoneview_load_controls(screen);
            screen->phoneview.edit_mode = true;
            screen->phoneview.capture_mode = false;
            screen->phoneview.dragging = false;
            screen->phoneview.drag_index = -1;
            sc_phoneview_ui_set_edit_mode(screen->phoneview.ui, true);
            sc_phoneview_ui_set_capture_mode(screen->phoneview.ui, false);
            sc_screen_render(screen, false);
            break;

        case SC_PHONEVIEW_UI_ACTION_ADD:
            if (!screen->phoneview.edit_mode) {
                break;
            }
            screen->phoneview.capture_mode = true;
            screen->phoneview.dragging = false;
            screen->phoneview.drag_index = -1;
            sc_phoneview_ui_set_capture_mode(screen->phoneview.ui, true);
            sc_screen_render(screen, false);
            break;

        case SC_PHONEVIEW_UI_ACTION_SAVE:
            if (screen->phoneview.edit_mode) {
                phoneview_save_controls(screen);
            }
            break;

        case SC_PHONEVIEW_UI_ACTION_DONE:
            screen->phoneview.capture_mode = false;
            screen->phoneview.edit_mode = false;
            screen->phoneview.dragging = false;
            screen->phoneview.drag_index = -1;
            phoneview_save_controls(screen);
            sc_phoneview_ui_set_capture_mode(screen->phoneview.ui, false);
            sc_phoneview_ui_set_edit_mode(screen->phoneview.ui, false);
            sc_screen_render(screen, false);
            break;

        case SC_PHONEVIEW_UI_ACTION_CLOSE:
            sc_push_event(SDL_EVENT_QUIT);
            break;
    }
}

static bool
phoneview_handle_event(struct sc_screen *screen, const SDL_Event *event) {
    if (!screen->phoneview.enabled) {
        return false;
    }

    if (!screen->phoneview.edit_mode) {
        switch (event->type) {
            case SDL_EVENT_KEY_DOWN:
            case SDL_EVENT_KEY_UP:
                if (phoneview_handle_mapped_keyboard(screen, &event->key)) {
                    return true;
                }
                break;
            case SDL_EVENT_MOUSE_BUTTON_DOWN:
            case SDL_EVENT_MOUSE_BUTTON_UP:
                if (phoneview_handle_mapped_mouse(screen, &event->button)) {
                    return true;
                }
                break;
            case SDL_EVENT_MOUSE_WHEEL:
                if (phoneview_handle_mapped_wheel(screen, &event->wheel)) {
                    return true;
                }
                break;
            default:
                break;
        }
    }

    if (event->type == SDL_EVENT_KEY_DOWN) {
        if (!screen->phoneview.edit_mode
                || !screen->phoneview.capture_mode) {
            return screen->phoneview.edit_mode;
        }

        if (event->key.key == SDLK_ESCAPE) {
            screen->phoneview.capture_mode = false;
            sc_phoneview_ui_set_capture_mode(screen->phoneview.ui, false);
            return true;
        }

        phoneview_capture_keyboard(screen, &event->key);
        return true;
    }

    if (event->type == SDL_EVENT_KEY_UP
            && screen->phoneview.edit_mode) {
        return true;
    }

    if (event->type == SDL_EVENT_MOUSE_WHEEL
            && screen->phoneview.edit_mode) {
        if (screen->phoneview.capture_mode) {
            phoneview_capture_wheel(screen, event->wheel.x, event->wheel.y);
        }
        return true;
    }

    if (event->type == SDL_EVENT_MOUSE_BUTTON_DOWN) {
        float x = event->button.x;
        float y = event->button.y;

        if (screen->phoneview.edit_mode && screen->phoneview.capture_mode) {
            if (event->button.button == SDL_BUTTON_LEFT
                    || event->button.button == SDL_BUTTON_RIGHT
                    || event->button.button == SDL_BUTTON_MIDDLE
                    || event->button.button == SDL_BUTTON_X1
                    || event->button.button == SDL_BUTTON_X2) {
                phoneview_capture_mouse(screen, event->button.button);
            }
            return true;
        }

        if (event->button.button == SDL_BUTTON_RIGHT
                && screen->phoneview.edit_mode) {
            struct sc_size size = sc_sdl_get_window_size(screen->window);
            int index = phoneview_hit_control(
                screen, x, y, (float) size.width, (float) size.height);
            if (index >= 0) {
                for (size_t i = (size_t) index;
                     i + 1 < screen->phoneview.count; ++i) {
                    screen->phoneview.controls[i] =
                        screen->phoneview.controls[i + 1];
                }
                screen->phoneview.count--;
                phoneview_save_controls(screen);
                sc_screen_render(screen, false);
            }
            return true;
        }

        if (event->button.button == SDL_BUTTON_LEFT
                && screen->phoneview.edit_mode) {
            struct sc_size size = sc_sdl_get_window_size(screen->window);
            int index = phoneview_hit_control(
                screen, x, y, (float) size.width, (float) size.height);
            if (index >= 0) {
                screen->phoneview.dragging = true;
                screen->phoneview.drag_index = index;
            }
            return true;
        }

        if (screen->phoneview.edit_mode) {
            return true;
        }
    }

    if (event->type == SDL_EVENT_MOUSE_MOTION
            && screen->phoneview.edit_mode) {
        if (!screen->phoneview.dragging) {
            return true;
        }

        struct sc_size size = sc_sdl_get_window_size(screen->window);
        float x = SDL_clamp(event->motion.x, 0.f, (float) size.width);
        float y = SDL_clamp(event->motion.y, 0.f, (float) size.height);

        if (screen->phoneview.drag_index >= 0
                && (size_t) screen->phoneview.drag_index < screen->phoneview.count) {
            struct sc_phoneview_control *control =
                &screen->phoneview.controls[screen->phoneview.drag_index];

            control->x = SDL_clamp(x / MAX(1.f, (float) size.width), 0.f, 1.f);
            control->y = SDL_clamp(y / MAX(1.f, (float) size.height), 0.f, 1.f);
        }
        return true;
    }

    if (event->type == SDL_EVENT_MOUSE_BUTTON_UP
            && event->button.button == SDL_BUTTON_LEFT
            && screen->phoneview.edit_mode) {
        if (screen->phoneview.dragging) {
            screen->phoneview.dragging = false;
            screen->phoneview.drag_index = -1;
            phoneview_save_controls(screen);
        }
        return true;
    }

    return false;
}

static void
set_aspect_ratio(struct sc_screen *screen, struct sc_size content_size) {
    assert(content_size.width && content_size.height);

    if (screen->window_aspect_ratio_lock) {
        float ar = (float) content_size.width / content_size.height;
        bool ok = SDL_SetWindowAspectRatio(screen->window, ar, ar);
        if (!ok) {
            LOGW("Could not set window aspect ratio: %s", SDL_GetError());
        }
    }
}

static inline struct sc_size
get_oriented_size(struct sc_size size, enum sc_orientation orientation) {
    struct sc_size oriented_size;
    if (sc_orientation_is_swap(orientation)) {
        oriented_size.width = size.height;
        oriented_size.height = size.width;
    } else {
        oriented_size.width = size.width;
        oriented_size.height = size.height;
    }
    return oriented_size;
}

static inline bool
is_windowed(struct sc_screen *screen) {
    if (screen->phoneview.ui) {
        return true;
    }

    return !(SDL_GetWindowFlags(screen->window) & (SDL_WINDOW_FULLSCREEN
                                                 | SDL_WINDOW_MINIMIZED
                                                 | SDL_WINDOW_MAXIMIZED));
}

// get the preferred display bounds (i.e. the screen bounds with some margins)
static bool
get_preferred_display_bounds(struct sc_size *bounds) {
    SDL_Rect rect;
    SDL_DisplayID display = SDL_GetPrimaryDisplay();
    if (!display) {
        LOGW("Could not get primary display: %s", SDL_GetError());
        return false;
    }

    bool ok = SDL_GetDisplayUsableBounds(display, &rect);
    if (!ok) {
        LOGW("Could not get display usable bounds: %s", SDL_GetError());
        return false;
    }

    bounds->width = MAX(0, rect.w - DISPLAY_MARGINS);
    bounds->height = MAX(0, rect.h - DISPLAY_MARGINS);
    return true;
}

static bool
is_optimal_size(struct sc_size current_size, struct sc_size content_size) {
    // The size is optimal if we can recompute one dimension of the current
    // size from the other
    return current_size.height == (uint32_t) current_size.width
                                * content_size.height / content_size.width
        || current_size.width == (uint32_t) current_size.height
                               * content_size.width / content_size.height;
}

// return the optimal size of the window, with the following constraints:
//  - it attempts to keep at least one dimension of the current_size (i.e. it
//    crops the black borders)
//  - it keeps the aspect ratio
//  - it scales down to make it fit in the display_size
static struct sc_size
get_optimal_size(struct sc_size current_size, struct sc_size content_size,
                 bool within_display_bounds) {
    if (content_size.width == 0 || content_size.height == 0) {
        // avoid division by 0
        return current_size;
    }

    struct sc_size window_size;

    struct sc_size display_size;
    if (!within_display_bounds ||
            !get_preferred_display_bounds(&display_size)) {
        // do not constraint the size
        window_size = current_size;
    } else {
        window_size.width = MIN(current_size.width, display_size.width);
        window_size.height = MIN(current_size.height, display_size.height);
    }

    if (is_optimal_size(window_size, content_size)) {
        return window_size;
    }

    bool keep_width = (uint32_t) content_size.width * window_size.height
                    > (uint32_t) content_size.height * window_size.width;
    if (keep_width) {
        // remove black borders on top and bottom
        window_size.height = (uint32_t) content_size.height * window_size.width
                           / content_size.width;
    } else {
        // remove black borders on left and right (or none at all if it already
        // fits)
        window_size.width = (uint32_t) content_size.width * window_size.height
                          / content_size.height;
    }

    return window_size;
}

// initially, there is no current size, so use the frame size as current size
// req_width and req_height, if not 0, are the sizes requested by the user
static inline struct sc_size
get_initial_optimal_size(struct sc_size content_size, uint16_t req_width,
                         uint16_t req_height) {
    struct sc_size window_size;
    if (!req_width && !req_height) {
        window_size = get_optimal_size(content_size, content_size, true);
    } else {
        if (req_width) {
            window_size.width = req_width;
        } else {
            // compute from the requested height
            window_size.width = (uint32_t) req_height * content_size.width
                              / content_size.height;
        }
        if (req_height) {
            window_size.height = req_height;
        } else {
            // compute from the requested width
            window_size.height = (uint32_t) req_width * content_size.height
                               / content_size.width;
        }
    }
    return window_size;
}

static inline void
sc_screen_track_resize(struct sc_screen *screen, struct sc_size size) {
    LOGV("Track resize: %" PRIu16 "x%" PRIu16, size.width, size.height);
    screen->resize_tracker.time = sc_tick_now();
    screen->resize_tracker.size = size;
}

static inline bool
sc_screen_is_relative_mode(struct sc_screen *screen) {
    // screen->im.mp may be NULL if --no-control
    return screen->im.mp && screen->im.mp->relative_mode;
}

static void
compute_content_rect(struct sc_size window_size, struct sc_size content_size,
                     bool is_icon, enum sc_render_fit render_fit,
                     bool phoneview,
                     SDL_FRect *rect) {
    if (is_icon) {
        if (content_size.width <= window_size.width
                && content_size.height <= window_size.height) {
            // Center without upscaling
            rect->x = (window_size.width - content_size.width) / 2.f;
            rect->y = (window_size.height - content_size.height) / 2.f;
            rect->w = content_size.width;
            rect->h = content_size.height;
            return;
        }
    } else if (render_fit == SC_RENDER_FIT_UNSCALED) {
        // Cast to float first because input sizes are unsigned
        float x = ((float) window_size.width - content_size.width) / 2.f;
        float y = ((float) window_size.height - content_size.height) / 2.f;
        rect->x = MAX(0, x);
        rect->y = MAX(0, y);
        rect->w = content_size.width;
        rect->h = content_size.height;
        return;
    } else if (render_fit == SC_RENDER_FIT_STRETCHED) {
        rect->x = 0;
        rect->y = 0;
        rect->w = window_size.width;
        rect->h = window_size.height;
        return;
    } else if (phoneview) {
        /*
         * Preserve the Android aspect ratio without centering it vertically.
         * The video starts directly below the PhoneView toolbar.
         */
        double window_ratio =
            window_size.height > 0
                ? (double) window_size.width / window_size.height
                : 0.0;
        double content_ratio =
            content_size.height > 0
                ? (double) content_size.width / content_size.height
                : 0.0;

        rect->x = 0;
        rect->y = 0;

        if (window_ratio > content_ratio) {
            rect->h = window_size.height;
            rect->w = (float) window_size.height * content_ratio;
        } else {
            rect->w = window_size.width;
            rect->h = (float) window_size.width / content_ratio;
        }

        return;
    }

    assert(is_icon || render_fit == SC_RENDER_FIT_LETTERBOX);

    if (is_optimal_size(window_size, content_size)) {
        rect->x = 0;
        rect->y = 0;
        rect->w = window_size.width;
        rect->h = window_size.height;
        return;
    }

    bool keep_width = (uint32_t) content_size.width * window_size.height
                    > (uint32_t) content_size.height * window_size.width;
    if (keep_width) {
        rect->x = 0;
        rect->w = window_size.width;
        rect->h = (float) window_size.width * content_size.height
                                            / content_size.width;
        rect->y = (window_size.height - rect->h) / 2.f;
    } else {
        rect->y = 0;
        rect->h = window_size.height;
        rect->w = (float) window_size.height * content_size.width
                                             / content_size.height;
        rect->x = (window_size.width - rect->w) / 2.f;
    }
}

static void
sc_screen_update_content_rect(struct sc_screen *screen) {
    // Only upscale video frames, not icon
    bool is_icon = !screen->video || screen->disconnected;

    struct sc_size window_size = sc_sdl_get_window_size(screen->window);

    compute_content_rect(window_size,
                         screen->content_size,
                         is_icon,
                         screen->render_fit,
                         screen->phoneview.ui != NULL,
                         &screen->rect);
}

// render the texture to the renderer
//
// Set the update_content_rect flag if the window or content size may have
// changed, so that the content rectangle is recomputed
static void
sc_screen_render(struct sc_screen *screen, bool update_content_rect) {
    assert(screen->window_shown);

    if (update_content_rect) {
        sc_screen_update_content_rect(screen);
    }

    SDL_Renderer *renderer = screen->renderer;
    struct sc_screen_bg_color bg = screen->bg;
    SDL_SetRenderDrawColor(renderer, bg.r, bg.g, bg.b, 0);
    sc_sdl_render_clear(renderer);

    SDL_Texture *texture = screen->tex.texture;
    if (!texture) {
        goto end;
    }

    float scale = SDL_GetWindowPixelDensity(screen->window);
    if (scale == 0) {
        // Just in case, but in practice the function can only fail when window
        // is invalid
        LOGE("Cannot get scale value: %s", SDL_GetError());
        scale = 1;
    }

    SDL_FRect geometry = {
        .x = screen->rect.x * scale,
        .y = screen->rect.y * scale,
        .w = screen->rect.w * scale,
        .h = screen->rect.h * scale,
    };
    enum sc_orientation orientation = screen->orientation;

    bool ok = false;
    if (orientation == SC_ORIENTATION_0) {
        // always align to a physical pixel
        geometry.x = (int32_t) geometry.x;
        geometry.y = (int32_t) geometry.y;
        ok = SDL_RenderTexture(renderer, texture, NULL, &geometry);
    } else {
        unsigned cw_rotation = sc_orientation_get_rotation(orientation);
        double angle = 90 * cw_rotation;

        SDL_FRect *dstrect = NULL;
        SDL_FRect rect;
        if (sc_orientation_is_swap(orientation)) {
            rect.x = geometry.x + (geometry.w - geometry.h) / 2.f;
            rect.y = geometry.y + (geometry.h - geometry.w) / 2.f;
            rect.w = geometry.h;
            rect.h = geometry.w;
            dstrect = &rect;
        } else {
            dstrect = &geometry;
        }

        SDL_FlipMode flip = sc_orientation_is_mirror(orientation)
                              ? SDL_FLIP_HORIZONTAL : 0;

        // always align to a physical pixel
        dstrect->x = (int32_t) dstrect->x;
        dstrect->y = (int32_t) dstrect->y;
        ok = SDL_RenderTextureRotated(renderer, texture, NULL, dstrect, angle,
                                      NULL, flip);
    }

    if (!ok) {
        LOGE("Could not render texture: %s", SDL_GetError());
    }

end:
    phoneview_render_controls(screen);
    sc_sdl_render_present(renderer);
}

static void
sc_screen_request_resize_display(struct sc_screen *screen, uint16_t width,
                                 uint16_t height) {
    assert(screen->flex_display);
    assert(!screen->camera);
    if (sc_orientation_is_swap(screen->orientation)) {
        uint16_t tmp = width;
        width = height;
        height = tmp;
    }

    LOGV("resize_display(%" PRIu16 ", %" PRIu16 ")", width, height);
    sc_controller_resize_display(screen->controller, width, height);
}

static void
sc_screen_on_resize(struct sc_screen *screen, const SDL_WindowEvent *event) {
    // This event can be triggered before the window is shown
    if (!screen->window_shown) {
        return;
    }

    if (event->type == SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED) {
        sc_screen_render(screen, true);
    } else {
        assert(event->type == SDL_EVENT_WINDOW_RESIZED);
        if (screen->flex_display) {
            assert(!(event->data1 & ~0xFFFF));
            assert(!(event->data2 & ~0xFFFF));
            uint16_t width = event->data1;
            uint16_t height = event->data2;

            struct sc_resize_tracker *tracker = &screen->resize_tracker;
            if (tracker->time
                    && sc_tick_now() >= tracker->time + SC_TICK_FROM_MS(3000)) {
                // Remove obsolete request
                tracker->time = 0;
            }
            if (tracker->time && tracker->size.width == width
                              && tracker->size.height == height) {
                // This resize event is the result of a previous (recent) resize
                // request triggered by a change in the frame's dimensions.
                LOGV("Ignore local resize: %" PRIu16 "x%" PRIu16,
                     width, height);
                tracker->time = 0;
            } else {
                sc_screen_request_resize_display(screen, width, height);
            }
        }
    }
}

#if defined(__APPLE__) || defined(_WIN32)
# define CONTINUOUS_RESIZING_WORKAROUND
#endif

#ifdef CONTINUOUS_RESIZING_WORKAROUND
// On Windows and MacOS, resizing blocks the event loop, so resizing events are
// not triggered. As a workaround, handle them in an event handler.
//
// <https://bugzilla.libsdl.org/show_bug.cgi?id=2077>
// <https://stackoverflow.com/a/40693139/1987178>
static bool
event_watcher(void *data, SDL_Event *event) {
    struct sc_screen *screen = data;
    assert(screen->video);

    if (event->type == SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED
            || event->type == SDL_EVENT_WINDOW_RESIZED) {
        // In practice, it seems to always be called from the same thread in
        // that specific case. Anyway, it's just a workaround.
        sc_screen_on_resize(screen, &event->window);
    }

    return true;
}
#endif

static bool
sc_screen_frame_sink_open(struct sc_frame_sink *sink,
                          const AVCodecContext *ctx,
                          const struct sc_stream_session *session) {
    assert(ctx->pix_fmt == AV_PIX_FMT_YUV420P);

    struct sc_screen *screen = DOWNCAST(sink);

    if (ctx->width <= 0 || ctx->width > 0xFFFF
            || ctx->height <= 0 || ctx->height > 0xFFFF) {
        LOGE("Invalid video size: %dx%d", ctx->width, ctx->height);
        return false;
    }

    screen->current_session = *session;

    assert(session->video.width && session->video.height);
    if (session->video.width > 0xFFFF || session->video.height > 0xFFFF) {
        LOGE("Size too large: %" PRIu32 "x%" PRIu32, session->video.width,
                                                     session->video.height);
        return false;
    }

    struct sc_size *size = malloc(sizeof(*size));
    if (!size) {
        LOG_OOM();
        return false;
    }
    size->width = session->video.width;
    size->height = session->video.height;

    bool ok = sc_push_event_with_data(SC_EVENT_OPEN_WINDOW, size);
    if (!ok) {
        free(size);
        return false;
    }

#ifndef NDEBUG
    screen->open = true;
#endif

    // nothing to do, the screen is already open on the main thread
    return true;
}

static void
sc_screen_frame_sink_close(struct sc_frame_sink *sink) {
    struct sc_screen *screen = DOWNCAST(sink);
    (void) screen;
#ifndef NDEBUG
    screen->open = false;
#endif

    // nothing to do, the screen lifecycle is not managed by the frame producer
}

static bool
sc_screen_frame_sink_push(struct sc_frame_sink *sink, const AVFrame *frame) {
    struct sc_screen *screen = DOWNCAST(sink);
    assert(screen->video);

    sc_mutex_lock(&screen->mutex);
    bool previous_skipped = sc_frame_buffer_has_frame(&screen->fb);
    bool ok = sc_frame_buffer_push(&screen->fb, frame);
    screen->prevent_auto_resize = screen->current_session.video.client_resized;
    sc_mutex_unlock(&screen->mutex);
    if (!ok) {
        return false;
    }

    if (previous_skipped) {
        sc_fps_counter_add_skipped_frame(&screen->fps_counter);
        // The SC_EVENT_NEW_FRAME triggered for the previous frame will consume
        // this new frame instead
    } else {
        // Post the event on the UI thread
        bool ok = sc_push_event(SC_EVENT_NEW_FRAME);
        if (!ok) {
            return false;
        }
    }

    return true;
}

static bool
sc_screen_frame_sink_push_session(struct sc_frame_sink *sink,
                                  const struct sc_stream_session *session) {
    struct sc_screen *screen = DOWNCAST(sink);
    screen->current_session = *session;
    return true;
}

static void
phoneview_set_window_size(struct sc_screen *screen,
                          struct sc_size video_size) {
    if (screen->phoneview.ui) {
        /*
         * The GTK top-level window belongs to the user. After it is shown,
         * content/orientation changes must resize only the embedded video
         * child, not move or resize the outer desktop window.
         */
        if (!screen->window_shown) {
            sc_phoneview_ui_set_window_size(screen->phoneview.ui,
                                            video_size.width,
                                            video_size.height);
        } else {
            sc_phoneview_ui_pump_events(screen->phoneview.ui);
        }
    } else {
        sc_sdl_set_window_size(screen->window, video_size);
    }
}

static void
phoneview_set_window_position(struct sc_screen *screen,
                              struct sc_point position) {
    if (screen->phoneview.ui) {
        sc_phoneview_ui_set_window_position(screen->phoneview.ui,
                                            position.x,
                                            position.y);
    } else {
        phoneview_set_window_position(screen, position);
    }
}

static void
phoneview_show_window(struct sc_screen *screen) {
    if (screen->phoneview.ui) {
        sc_phoneview_ui_show(screen->phoneview.ui);
    } else {
        phoneview_show_window(screen);
    }
}

static void
phoneview_hide_window(struct sc_screen *screen) {
    if (screen->phoneview.ui) {
        sc_phoneview_ui_hide(screen->phoneview.ui);
    } else {
        phoneview_hide_window(screen);
    }
}

static void
phoneview_toggle_fullscreen(struct sc_screen *screen, bool fullscreen) {
    if (screen->phoneview.ui) {
        sc_phoneview_ui_set_fullscreen(screen->phoneview.ui, fullscreen);
        return;
    }

    bool ok = SDL_SetWindowFullscreen(screen->window, fullscreen);
    if (!ok) {
        LOGW("Could not switch fullscreen mode: %s", SDL_GetError());
    }
}

static void
phoneview_destroy_window(struct sc_screen *screen) {
    if (screen->phoneview.ui) {
        sc_phoneview_ui_destroy(screen->phoneview.ui);
        screen->phoneview.ui = NULL;
        screen->window = NULL;
    } else if (screen->window) {
        SDL_DestroyWindow(screen->window);
        screen->window = NULL;
    }
}

bool
sc_screen_init(struct sc_screen *screen,
               const struct sc_screen_params *params) {
    screen->controller = params->controller;

    screen->resize_pending = false;
    screen->window_shown = false;
    screen->paused = false;
    screen->resume_frame = NULL;
    screen->orientation = SC_ORIENTATION_0;
    screen->disconnected = false;
    screen->disconnect_started = false;

    memset(&screen->phoneview, 0, sizeof(screen->phoneview));
    screen->phoneview.enabled = getenv("PHONEVIEW_MAPPING") != NULL;
    screen->phoneview.ui = NULL;
    screen->phoneview.drag_index = -1;
    if (screen->phoneview.enabled) {
        phoneview_load_controls(screen);
    }

    screen->video = params->video;
    screen->camera = params->camera;
    screen->window_aspect_ratio_lock = params->window_aspect_ratio_lock;
    screen->render_fit = params->render_fit;
    screen->flex_display = params->flex_display;

    screen->bg.r = (params->background_color >> 16) & 0xFF;
    screen->bg.g = (params->background_color >> 8) & 0xFF;
    screen->bg.b = params->background_color & 0xFF;

    screen->req.x = params->window_x;
    screen->req.y = params->window_y;
    screen->req.width = params->window_width;
    screen->req.height = params->window_height;
    screen->req.fullscreen = params->fullscreen;
    screen->req.start_fps_counter = params->start_fps_counter;

    screen->prevent_auto_resize = false;

    screen->resize_tracker.time = 0;
    screen->resize_tracker.size.width = 0;
    screen->resize_tracker.size.height = 0;

    bool ok = sc_mutex_init(&screen->mutex);
    if (!ok) {
        return false;
    }

    ok = sc_frame_buffer_init(&screen->fb);
    if (!ok) {
        goto error_destroy_mutex;
    }

    if (!sc_fps_counter_init(&screen->fps_counter)) {
        goto error_destroy_frame_buffer;
    }

    if (screen->video) {
        screen->orientation = params->orientation;
        if (screen->orientation != SC_ORIENTATION_0) {
            LOGI("Initial display orientation set to %s",
                 sc_orientation_get_name(screen->orientation));
        }
    }

    // Always create the window hidden to prevent blinking during initialization
    uint32_t window_flags = SDL_WINDOW_HIGH_PIXEL_DENSITY | SDL_WINDOW_HIDDEN;
    if (params->always_on_top) {
        window_flags |= SDL_WINDOW_ALWAYS_ON_TOP;
    }
    if (params->window_borderless) {
        window_flags |= SDL_WINDOW_BORDERLESS;
    }
    if (params->video) {
        // The window will be shown on first frame
        window_flags |= SDL_WINDOW_RESIZABLE;
    }

    const char *title = params->window_title;
    assert(title);

    int x = SDL_WINDOWPOS_UNDEFINED;
    int y = SDL_WINDOWPOS_UNDEFINED;
    int width = 256;
    int height = 256;
    if (params->window_x != SC_WINDOW_POSITION_UNDEFINED) {
        x = params->window_x;
    }
    if (params->window_y != SC_WINDOW_POSITION_UNDEFINED) {
        y = params->window_y;
    }
    if (params->window_width) {
        width = params->window_width;
    }
    if (params->window_height) {
        height = params->window_height;
    }

    // PhoneView uses a real GTK top-level window and a native SDL child
    // window for the Android video surface. This keeps the toolbar outside
    // the video renderer while remaining part of the same application window.
    if (screen->phoneview.enabled && params->video) {
        screen->phoneview.ui =
            sc_phoneview_ui_create(title,
                                   width,
                                   height,
                                   params->always_on_top,
                                   !params->window_borderless,
                                   phoneview_ui_action_cb,
                                   screen);
        if (!screen->phoneview.ui) {
            goto error_destroy_fps_counter;
        }

        screen->window =
            sc_phoneview_ui_get_video_window(screen->phoneview.ui);
        if (!screen->window) {
            LOGE("Could not create PhoneView video surface");
            goto error_destroy_window;
        }
    } else {
        screen->window =
            sc_sdl_create_window(title, x, y, width, height, window_flags);
        if (!screen->window) {
            LOGE("Could not create window: %s", SDL_GetError());
            goto error_destroy_fps_counter;
        }
    }

    screen->renderer = SDL_CreateRenderer(screen->window, NULL);
    if (!screen->renderer) {
        LOGE("Could not create renderer: %s", SDL_GetError());
        goto error_destroy_window;
    }

#ifdef SC_DISPLAY_FORCE_OPENGL_CORE_PROFILE
    screen->gl_context = NULL;

    // starts with "opengl"
    const char *renderer_name = SDL_GetRendererName(screen->renderer);
    bool use_opengl = renderer_name && !strncmp(renderer_name, "opengl", 6);
    if (use_opengl) {
        // Persuade macOS to give us something better than OpenGL 2.1.
        // If we create a Core Profile context, we get the best OpenGL version.
        bool ok = SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK,
                                      SDL_GL_CONTEXT_PROFILE_CORE);
        if (!ok) {
            LOGW("Could not set a GL Core Profile Context");
        }

        LOGD("Creating OpenGL Core Profile context");
        screen->gl_context = SDL_GL_CreateContext(screen->window);
        if (!screen->gl_context) {
            LOGE("Could not create OpenGL context: %s", SDL_GetError());
            goto error_destroy_renderer;
        }
    }
#endif

    bool mipmaps = params->video;
    ok = sc_texture_init(&screen->tex, screen->renderer, mipmaps);
    if (!ok) {
        goto error_destroy_renderer;
    }

    ok = SDL_StartTextInput(screen->window);
    if (!ok) {
        LOGE("Could not enable text input: %s", SDL_GetError());
        goto error_destroy_texture;
    }

    SDL_Surface *icon = sc_icon_load(SC_ICON_FILENAME_SCRCPY);
    if (icon) {
        if (!SDL_SetWindowIcon(screen->window, icon)) {
            LOGW("Could not set window icon: %s", SDL_GetError());
        }

        if (!params->video) {
            screen->content_size.width = icon->w;
            screen->content_size.height = icon->h;
            ok = sc_texture_set_from_surface(&screen->tex, icon);
            if (!ok) {
                LOGE("Could not set icon: %s", SDL_GetError());
            }
        }

        sc_icon_destroy(icon);
    } else {
        // not fatal
        LOGE("Could not load icon");

        if (!params->video) {
            // Make sure the content size is initialized
            screen->content_size.width = 256;
            screen->content_size.height = 256;
        }
    }

    screen->frame = av_frame_alloc();
    if (!screen->frame) {
        LOG_OOM();
        goto error_destroy_texture;
    }

    struct sc_input_manager_params im_params = {
        .controller = params->controller,
        .fp = params->fp,
        .screen = screen,
        .kp = params->kp,
        .mp = params->mp,
        .gp = params->gp,
        .camera = params->camera,
        .mouse_bindings = params->mouse_bindings,
        .legacy_paste = params->legacy_paste,
        .clipboard_autosync = params->clipboard_autosync,
        .shortcut_mods = params->shortcut_mods,
    };

    sc_input_manager_init(&screen->im, &im_params);

    // Initialize even if not used for simplicity
    sc_mouse_capture_init(&screen->mc, screen->window, params->shortcut_mods);

#ifdef CONTINUOUS_RESIZING_WORKAROUND
    if (screen->video) {
        ok = SDL_AddEventWatch(event_watcher, screen);
        if (!ok) {
            LOGW("Could not add event watcher for continuous resizing: %s",
                 SDL_GetError());
        }
    }
#endif

    memset(&screen->current_session, 0, sizeof(screen->current_session));

    static const struct sc_frame_sink_ops ops = {
        .open = sc_screen_frame_sink_open,
        .close = sc_screen_frame_sink_close,
        .push = sc_screen_frame_sink_push,
        .push_session = sc_screen_frame_sink_push_session,
    };

    screen->frame_sink.ops = &ops;

#ifndef NDEBUG
    screen->open = false;
#endif

    if (!screen->video) {
        // Show the window immediately
        screen->window_shown = true;
        phoneview_show_window(screen);

        if (sc_screen_is_relative_mode(screen)) {
            // Capture mouse immediately if video mirroring is disabled
            sc_mouse_capture_set_active(&screen->mc, true);
        }
    }

    return true;

error_destroy_texture:
    sc_texture_destroy(&screen->tex);
error_destroy_renderer:
#ifdef SC_DISPLAY_FORCE_OPENGL_CORE_PROFILE
    if (screen->gl_context) {
        SDL_GL_DestroyContext(screen->gl_context);
    }
#endif
    SDL_DestroyRenderer(screen->renderer);
error_destroy_window:
    phoneview_destroy_window(screen);
error_destroy_fps_counter:
    sc_fps_counter_destroy(&screen->fps_counter);
error_destroy_frame_buffer:
    sc_frame_buffer_destroy(&screen->fb);
error_destroy_mutex:
    sc_mutex_destroy(&screen->mutex);

    return false;
}

static void
sc_screen_show_initial_window(struct sc_screen *screen) {
    int x = screen->req.x != SC_WINDOW_POSITION_UNDEFINED
          ? screen->req.x : (int) SDL_WINDOWPOS_CENTERED;
    int y = screen->req.y != SC_WINDOW_POSITION_UNDEFINED
          ? screen->req.y : (int) SDL_WINDOWPOS_CENTERED;
    struct sc_point position = {
        .x = x,
        .y = y,
    };

    struct sc_size window_size =
        get_initial_optimal_size(screen->content_size, screen->req.width,
                                                       screen->req.height);

    if (screen->flex_display
            && window_size.width == screen->content_size.width
            && window_size.height == screen->content_size.height) {
        // Avoid sending an unnecessary initial "resize display" request to the
        // server if the size has not changed.
        sc_screen_track_resize(screen, window_size);
    }

    assert(is_windowed(screen));
    set_aspect_ratio(screen, screen->content_size);
    phoneview_set_window_size(screen, window_size);
    phoneview_set_window_position(screen, position);

    if (screen->req.fullscreen) {
        sc_screen_toggle_fullscreen(screen);
    }

    if (screen->req.start_fps_counter) {
        sc_fps_counter_start(&screen->fps_counter);
    }

    screen->window_shown = true;
    phoneview_show_window(screen);
    sc_screen_update_content_rect(screen);
}

void
sc_screen_hide_window(struct sc_screen *screen) {
    phoneview_hide_window(screen);
    screen->window_shown = false;
}

void
sc_screen_interrupt(struct sc_screen *screen) {
    sc_fps_counter_interrupt(&screen->fps_counter);
}

static void
sc_screen_interrupt_disconnect(struct sc_screen *screen) {
    if (screen->disconnect_started) {
        sc_disconnect_interrupt(&screen->disconnect);
    }
}

void
sc_screen_join(struct sc_screen *screen) {
    sc_fps_counter_join(&screen->fps_counter);
    if (screen->disconnect_started) {
        sc_disconnect_join(&screen->disconnect);
    }
}

void
sc_screen_destroy(struct sc_screen *screen) {
#ifndef NDEBUG
    assert(!screen->open);
#endif
    if (screen->disconnect_started) {
        sc_disconnect_destroy(&screen->disconnect);
    }
    sc_texture_destroy(&screen->tex);
    av_frame_free(&screen->frame);
#ifdef SC_DISPLAY_FORCE_OPENGL_CORE_PROFILE
    SDL_GL_DestroyContext(screen->gl_context);
#endif
    SDL_DestroyRenderer(screen->renderer);
    phoneview_destroy_window(screen);
    sc_fps_counter_destroy(&screen->fps_counter);
    sc_frame_buffer_destroy(&screen->fb);
    sc_mutex_destroy(&screen->mutex);

    SDL_Event event;
    bool has_event =
        sc_dequeue_event(SC_EVENT_DISCONNECTED_ICON_LOADED, &event);
    if (has_event) {
        assert(event.type == SC_EVENT_DISCONNECTED_ICON_LOADED);
        // The event was posted, but not handled, the icon must be freed
        SDL_Surface *dangling_icon = event.user.data1;
        sc_icon_destroy(dangling_icon);
    }

    has_event = sc_dequeue_event(SC_EVENT_OPEN_WINDOW, &event);
    if (has_event) {
        assert(event.type == SC_EVENT_OPEN_WINDOW);
        // The event was posted, but not handled, the size must be freed
        struct sc_size * size = event.user.data1;
        free(size);
    }
}

static void
resize_for_content(struct sc_screen *screen, struct sc_size old_content_size,
                   struct sc_size new_content_size) {
    assert(screen->video);

    struct sc_size target_size = new_content_size;
    if (!screen->flex_display) {
        struct sc_size window_size = sc_sdl_get_window_size(screen->window);
        // Scale proportionally
        target_size.width = (uint32_t) window_size.width * target_size.width
                          / old_content_size.width;
        target_size.height = (uint32_t) window_size.height * target_size.height
                           / old_content_size.height;
    }
    target_size = get_optimal_size(target_size, new_content_size, true);
    assert(is_windowed(screen));
    set_aspect_ratio(screen, new_content_size);
    phoneview_set_window_size(screen, target_size);
}

static void
set_content_size(struct sc_screen *screen, struct sc_size new_content_size,
                 bool resize) {
    assert(screen->video);

    if (resize) {
        if (is_windowed(screen)) {
            resize_for_content(screen, screen->content_size, new_content_size);
        } else if (screen->flex_display) {
            // Force a display resize, the client cannot resize in fullscreen
            struct sc_size size = sc_sdl_get_window_size(screen->window);
            sc_screen_request_resize_display(screen, size.width, size.height);
        } else if (!screen->resize_pending) {
            // Store the windowed size to be able to compute the optimal size
            // once fullscreen/maximized/minimized are disabled
            screen->windowed_content_size = screen->content_size;
            screen->resize_pending = true;
        }
    }

    screen->content_size = new_content_size;
}

static void
apply_pending_resize(struct sc_screen *screen) {
    assert(screen->video);

    assert(is_windowed(screen));
    if (screen->resize_pending) {
        resize_for_content(screen, screen->windowed_content_size,
                                   screen->content_size);
        screen->resize_pending = false;
    }
}

void
sc_screen_set_orientation(struct sc_screen *screen,
                          enum sc_orientation orientation) {
    assert(screen->video);

    if (orientation == screen->orientation) {
        return;
    }

    struct sc_size new_content_size =
        get_oriented_size(screen->frame_size, orientation);

    set_content_size(screen, new_content_size, true);

    screen->orientation = orientation;
    LOGI("Display orientation set to %s", sc_orientation_get_name(orientation));

    sc_screen_render(screen, true);
}

static bool
sc_screen_apply_frame(struct sc_screen *screen, bool can_resize) {
    assert(screen->video);
    assert(screen->window_shown);

    sc_fps_counter_add_rendered_frame(&screen->fps_counter);

    AVFrame *frame = screen->frame;
    struct sc_size new_frame_size = {frame->width, frame->height};

    if (!new_frame_size.width || !new_frame_size.height) {
        LOGE("Invalid frame size: %" PRIu32 "x%" PRIu32,
             new_frame_size.width, new_frame_size.height);
        return false;
    }

    if (screen->frame_size.width != new_frame_size.width
            || screen->frame_size.height != new_frame_size.height) {

        // frame dimension changed
        screen->frame_size = new_frame_size;

        struct sc_size new_content_size =
            get_oriented_size(new_frame_size, screen->orientation);

        if (screen->flex_display) {
            sc_screen_track_resize(screen, new_content_size);
        }

        set_content_size(screen, new_content_size, can_resize);
        sc_screen_update_content_rect(screen);
    }

    bool ok = sc_texture_set_from_frame(&screen->tex, frame);
    if (!ok) {
        return false;
    }

    sc_screen_render(screen, false);
    return true;
}

static bool
sc_screen_update_frame(struct sc_screen *screen) {
    assert(screen->video);

    if (screen->paused) {
        if (!screen->resume_frame) {
            screen->resume_frame = av_frame_alloc();
            if (!screen->resume_frame) {
                LOG_OOM();
                return false;
            }
        } else {
            av_frame_unref(screen->resume_frame);
        }
        sc_mutex_lock(&screen->mutex);
        sc_frame_buffer_consume(&screen->fb, screen->resume_frame);
        sc_mutex_unlock(&screen->mutex);
        return true;
    }

    av_frame_unref(screen->frame);
    sc_mutex_lock(&screen->mutex);
    sc_frame_buffer_consume(&screen->fb, screen->frame);
    // read with lock held
    bool can_resize = !screen->prevent_auto_resize;
    sc_mutex_unlock(&screen->mutex);
    return sc_screen_apply_frame(screen, can_resize);
}

void
sc_screen_set_paused(struct sc_screen *screen, bool paused) {
    assert(screen->video);

    if (!paused && !screen->paused) {
        // nothing to do
        return;
    }

    if (screen->paused && screen->resume_frame) {
        // If display screen was paused, refresh the frame immediately, even if
        // the new state is also paused.
        av_frame_free(&screen->frame);
        screen->frame = screen->resume_frame;
        screen->resume_frame = NULL;
        bool ok = sc_screen_apply_frame(screen, true);
        if (!ok) {
            LOGE("Resume frame update failed");
        }
    }

    if (!paused) {
        LOGI("Display screen unpaused");
    } else if (!screen->paused) {
        LOGI("Display screen paused");
    } else {
        LOGI("Display screen re-paused");
    }

    screen->paused = paused;
}

void
sc_screen_toggle_fullscreen(struct sc_screen *screen) {
    bool fullscreen = !(SDL_GetWindowFlags(screen->window) & SDL_WINDOW_FULLSCREEN);
    if (screen->phoneview.ui) {
        sc_phoneview_ui_set_fullscreen(screen->phoneview.ui, fullscreen);
        return;
    }

    bool ok = SDL_SetWindowFullscreen(screen->window, fullscreen);
    if (!ok) {
        LOGW("Could not switch fullscreen mode: %s", SDL_GetError());
        return;
    }

    LOGD("Requested %s mode", fullscreen ? "fullscreen" : "windowed");
}

void
sc_screen_resize_to_fit(struct sc_screen *screen) {
    assert(screen->video);

    if (!is_windowed(screen)) {
        return;
    }

    if (screen->render_fit == SC_RENDER_FIT_STRETCHED) {
        // nothing to do
        return;
    }

    struct sc_size window_size = sc_sdl_get_window_size(screen->window);

    if (screen->render_fit == SC_RENDER_FIT_UNSCALED) {
        struct sc_size content_size = screen->content_size;
        set_aspect_ratio(screen, content_size);
        phoneview_set_window_size(screen, content_size);

        int32_t x_offset = 0;
        if (content_size.width < window_size.width) {
            x_offset = (window_size.width - content_size.width) / 2;
        }
        int32_t y_offset = 0;
        if (content_size.height < window_size.height) {
            y_offset = (window_size.height - content_size.height) / 2;
        }
        assert(x_offset >= 0 && y_offset >= 0);
        if (x_offset || y_offset) {
            struct sc_point pos = sc_sdl_get_window_position(screen->window);
            pos.x += x_offset;
            pos.y += y_offset;
            phoneview_set_window_position(screen, pos);
        }

        LOGD("Resized to content size: %ux%u", content_size.width,
                                               content_size.height);
        return;
    }

    assert(screen->render_fit == SC_RENDER_FIT_LETTERBOX);

    struct sc_point point = sc_sdl_get_window_position(screen->window);

    struct sc_size optimal_size =
        get_optimal_size(window_size, screen->content_size, false);

    // Center the window related to the device screen
    assert(optimal_size.width <= window_size.width);
    assert(optimal_size.height <= window_size.height);

    struct sc_point new_position = {
        .x = point.x + (window_size.width - optimal_size.width) / 2,
        .y = point.y + (window_size.height - optimal_size.height) / 2,
    };

    set_aspect_ratio(screen, screen->content_size);
    phoneview_set_window_size(screen, optimal_size);
    phoneview_set_window_position(screen, new_position);
    LOGD("Resized to optimal size: %ux%u", optimal_size.width,
                                           optimal_size.height);
}

void
sc_screen_resize_to_pixel_perfect(struct sc_screen *screen) {
    assert(screen->video);

    if (!is_windowed(screen)) {
        return;
    }

    struct sc_size content_size = screen->content_size;
    set_aspect_ratio(screen, content_size);
    phoneview_set_window_size(screen, content_size);
    LOGD("Resized to pixel-perfect: %ux%u", content_size.width,
                                            content_size.height);
}

static void
sc_disconnect_on_icon_loaded(struct sc_disconnect *d, SDL_Surface *icon,
                             void *userdata) {
    (void) d;
    (void) userdata;

    bool ok = sc_push_event_with_data(SC_EVENT_DISCONNECTED_ICON_LOADED, icon);
    if (!ok) {
        sc_icon_destroy(icon);
    }
}

static void
sc_disconnect_on_timeout(struct sc_disconnect *d, void *userdata) {
    (void) d;
    (void) userdata;

    bool ok = sc_push_event(SC_EVENT_DISCONNECTED_TIMEOUT);
    (void) ok; // ignore failure
}

void
sc_screen_pump_ui_events(struct sc_screen *screen) {
    if (screen && screen->phoneview.ui) {
        sc_phoneview_ui_pump_events(screen->phoneview.ui);
    }
}

void
sc_screen_handle_event(struct sc_screen *screen, const SDL_Event *event) {
    switch (event->type) {
        case SC_EVENT_OPEN_WINDOW: {
            struct sc_size *size = event->user.data1;
            assert(size);

            screen->frame_size = *size;
            free(size);
            screen->content_size = get_oriented_size(screen->frame_size,
                                                     screen->orientation);
            sc_screen_show_initial_window(screen);

            if (sc_screen_is_relative_mode(screen)) {
                // Capture mouse on start
                sc_mouse_capture_set_active(&screen->mc, true);
            }

            sc_screen_render(screen, false);
            return;
        }
        case SC_EVENT_NEW_FRAME: {
            bool ok = sc_screen_update_frame(screen);
            if (!ok) {
                LOGE("Frame update failed\n");
            }
            return;
        }
        case SDL_EVENT_WINDOW_EXPOSED:
            sc_screen_render(screen, true);
            return;
// If defined, then the actions are already performed by the event watcher
#ifndef CONTINUOUS_RESIZING_WORKAROUND
        case SDL_EVENT_WINDOW_RESIZED:
        case SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED:
            sc_screen_on_resize(screen, &event->window);
            return;
#endif
        case SDL_EVENT_WINDOW_RESTORED:
            if (screen->video && is_windowed(screen)) {
                apply_pending_resize(screen);
                sc_screen_render(screen, true);
            }
            return;
        case SDL_EVENT_WINDOW_ENTER_FULLSCREEN:
            LOGD("Switched to fullscreen mode");
            assert(screen->video);
            return;
        case SDL_EVENT_WINDOW_LEAVE_FULLSCREEN:
            LOGD("Switched to windowed mode");
            assert(screen->video);
            if (is_windowed(screen)) {
                apply_pending_resize(screen);
                sc_screen_render(screen, true);
            }
            return;
        case SC_EVENT_DEVICE_DISCONNECTED:
            assert(!screen->disconnected);
            screen->disconnected = true;
            if (!screen->window_shown) {
                // No window open
                return;
            }

            sc_input_manager_handle_event(&screen->im, event);

            sc_texture_reset(&screen->tex);
            sc_screen_render(screen, true);

            sc_tick deadline = sc_tick_now() + SC_TICK_FROM_SEC(2);
            static const struct sc_disconnect_callbacks cbs = {
                .on_icon_loaded = sc_disconnect_on_icon_loaded,
                .on_timeout = sc_disconnect_on_timeout,
            };
            bool ok =
                sc_disconnect_start(&screen->disconnect, deadline, &cbs, NULL);
            if (ok) {
                screen->disconnect_started = true;
            }

            return;
    }

    if (phoneview_handle_event(screen, event)) {
        return;
    }

    if (sc_screen_is_relative_mode(screen)
            && sc_mouse_capture_handle_event(&screen->mc, event)) {
        // The mouse capture handler consumed the event
        return;
    }

    sc_input_manager_handle_event(&screen->im, event);
}

void
sc_screen_handle_disconnection(struct sc_screen *screen) {
    if (!screen->window_shown) {
        // No window open, quit immediately
        return;
    }

    if (!screen->disconnect_started) {
        // If sc_disconnect_start() failed, quit immediately
        return;
    }

    SDL_Event event;
    while (true) {
        if (!SDL_WaitEventTimeout(&event, 10)) {
            sc_screen_pump_ui_events(screen);
            continue;
        }
        sc_screen_pump_ui_events(screen);
        switch (event.type) {
            case SDL_EVENT_WINDOW_EXPOSED:
                sc_screen_render(screen, true);
                break;
            case SC_EVENT_DISCONNECTED_ICON_LOADED: {
                SDL_Surface *icon_disconnected = event.user.data1;
                assert(icon_disconnected);

                bool ok = sc_texture_set_from_surface(&screen->tex,
                                                      icon_disconnected);
                if (ok) {
                    screen->content_size.width = icon_disconnected->w;
                    screen->content_size.height = icon_disconnected->h;
                    sc_screen_render(screen, true);
                } else {
                    // not fatal
                    LOGE("Could not set disconnected icon");
                }

                sc_icon_destroy(icon_disconnected);
                break;
            }
            case SC_EVENT_DISCONNECTED_TIMEOUT:
                LOGD("Closing after device disconnection");
                return;
            case SDL_EVENT_QUIT:
                LOGD("User requested to quit");
                sc_screen_interrupt_disconnect(screen);
                return;
            default:
                sc_input_manager_handle_event(&screen->im, &event);
        }
    }
}

struct sc_point
sc_screen_convert_window_to_frame_coords(struct sc_screen *screen,
                                         int32_t x, int32_t y) {
    assert(screen->video);

    enum sc_orientation orientation = screen->orientation;

    int32_t w = screen->content_size.width;
    int32_t h = screen->content_size.height;

    // screen->rect must be initialized to avoid a division by zero
    assert(screen->rect.w && screen->rect.h);

    x = (int64_t) (x - screen->rect.x) * w / screen->rect.w;
    y = (int64_t) (y - screen->rect.y) * h / screen->rect.h;

    struct sc_point result;
    switch (orientation) {
        case SC_ORIENTATION_0:
            result.x = x;
            result.y = y;
            break;
        case SC_ORIENTATION_90:
            result.x = y;
            result.y = w - x;
            break;
        case SC_ORIENTATION_180:
            result.x = w - x;
            result.y = h - y;
            break;
        case SC_ORIENTATION_270:
            result.x = h - y;
            result.y = x;
            break;
        case SC_ORIENTATION_FLIP_0:
            result.x = w - x;
            result.y = y;
            break;
        case SC_ORIENTATION_FLIP_90:
            result.x = h - y;
            result.y = w - x;
            break;
        case SC_ORIENTATION_FLIP_180:
            result.x = x;
            result.y = h - y;
            break;
        default:
            assert(orientation == SC_ORIENTATION_FLIP_270);
            result.x = y;
            result.y = x;
            break;
    }

    return result;
}
