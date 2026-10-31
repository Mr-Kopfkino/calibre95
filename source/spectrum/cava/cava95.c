/* Thin, bounded ABI for the real CAVA core. GPL-3.0-or-later wrapper.
 * Original cavacore.c/.h is kept unchanged in source/cava-reference (MIT).
 */
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "cavacore.h"
#define API __declspec(dllexport)
#define MAX_BARS 64
#define MAX_SAMPLES 16384

typedef struct {
    struct cava_plan *plan;
    int bars, rate;
    double *input;
    double output[MAX_BARS];
} C95Cava;

static struct cava_plan *new_plan(int bars, int rate) {
    struct cava_plan *p;
    if (!c95_fft_available()) return NULL;
    c95_fft_failed();
    /* A smaller 20Hz visualizer benefits from faster envelope response than
       CAVA's high-refresh terminal default. No stereo duplication is needed. */
    p = cava_init(bars, rate, 1, 1, 0.58, 50, 10000, CAVA_SCALING_LINEAR);
    if (!p) return NULL;
    if (p->status) { free(p); return NULL; }
    if (c95_fft_failed()) { cava_destroy(p); free(p); return NULL; }
    p->framerate = 20.0;
    return p;
}

API void *c95_cava_create(int bars, int rate) {
    C95Cava *c;
    if (bars < 1 || bars > MAX_BARS || (rate != 22050 && rate != 24000)) return NULL;
    c = (C95Cava *)calloc(1, sizeof(*c));
    if (!c) return NULL;
    c->input = (double *)calloc(MAX_SAMPLES, sizeof(double));
    if (!c->input) { free(c); return NULL; }
    c->bars = bars; c->rate = rate;
    c->plan = new_plan(bars, rate);
    if (!c->plan) { free(c->input); free(c); return NULL; }
    return c;
}

API int c95_cava_process(void *handle, const float *input, int samples, float *output) {
    C95Cava *c = (C95Cava *)handle;
    int i;
    if (!c || !c->plan || !input || !output || samples < 0 || samples > MAX_SAMPLES)
        return -1;
    /* CAVA uses int16-scale doubles internally; decoder provides normalized PCM. */
    if (samples > c->plan->input_buffer_size) {
        input += samples - c->plan->input_buffer_size;
        samples = c->plan->input_buffer_size;
    }
    for (i = 0; i < samples; ++i) {
        double value = input[i];
        if (!isfinite(value)) value = 0.0;
        if (value > 1.0) value = 1.0;
        if (value < -1.0) value = -1.0;
        c->input[i] = value * 32768.0;
    }
    cava_execute(c->input, samples, c->output, c->plan);
    for (i = 0; i < c->bars; ++i) {
        double value = c->output[i];
        output[i] = (float)(!isfinite(value) || value < 0.0 ? 0.0 : value > 1.0 ? 1.0 : value);
    }
    return 0;
}

API int c95_cava_reset(void *handle) {
    C95Cava *c = (C95Cava *)handle;
    struct cava_plan *p;
    if (!c) return -1;
    p = new_plan(c->bars, c->rate);
    if (!p) return -1;
    cava_destroy(c->plan); free(c->plan);
    c->plan = p;
    memset(c->output, 0, sizeof(c->output));
    return 0;
}

API int c95_cava_cutoffs(void *handle, float *output) {
    C95Cava *c = (C95Cava *)handle;
    if (!c || !c->plan || !output) return -1;
    memcpy(output, c->plan->cut_off_frequency, (c->bars+1)*sizeof(float));
    return 0;
}

API void c95_cava_destroy(void *handle) {
    C95Cava *c = (C95Cava *)handle;
    if (!c) return;
    if (c->plan) { cava_destroy(c->plan); free(c->plan); }
    free(c->input); free(c);
}
