/* Original calibre95 FFT adapter. GPL-3.0-or-later.
 * Uses avutil already shipped with calibre; no FFTW library or code is linked.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>
#include <string.h>
#include "fftw3.h"
#include "libavutil/tx.h"

typedef int (*tx_init_type)(AVTXContext **, av_tx_fn *, enum AVTXType, int, int,
                            const void *, uint64_t);
typedef void (*tx_uninit_type)(AVTXContext **);
static tx_init_type tx_init;
static tx_uninit_type tx_uninit;
static INIT_ONCE tx_once = INIT_ONCE_STATIC_INIT;
static __declspec(thread) int failed;

struct c95_fft_plan {
    AVTXContext *context;
    av_tx_fn execute;
    double *input;
    fftw_complex *output;
    int count;
};

static BOOL CALLBACK bind_api(PINIT_ONCE once, PVOID param, PVOID *context) {
    HMODULE avutil = GetModuleHandleW(L"avutil-58.dll");
    (void)once; (void)param; (void)context;
    if (!avutil) return FALSE;
    tx_init = (tx_init_type)GetProcAddress(avutil, "av_tx_init");
    tx_uninit = (tx_uninit_type)GetProcAddress(avutil, "av_tx_uninit");
    return tx_init && tx_uninit;
}

int c95_fft_available(void) {
    return InitOnceExecuteOnce(&tx_once, bind_api, NULL, NULL) != 0;
}
int c95_fft_failed(void) { int result = failed; failed = 0; return result; }
double *fftw_alloc_real(size_t n) { return (double *)calloc(n, sizeof(double)); }
fftw_complex *fftw_alloc_complex(size_t n) {
    return (fftw_complex *)calloc(n, sizeof(fftw_complex));
}
void fftw_free(void *ptr) { free(ptr); }

fftw_plan fftw_plan_dft_r2c_1d(int n, double *input, fftw_complex *output, unsigned flags) {
    struct c95_fft_plan *plan = (struct c95_fft_plan *)calloc(1, sizeof(*plan));
    double scale = 1.0;
    (void)flags;
    if (!plan) { failed = 1; return NULL; }
    plan->input = input; plan->output = output; plan->count = n;
    if (!input || !output || !c95_fft_available() ||
        tx_init(&plan->context, &plan->execute, AV_TX_DOUBLE_RDFT, 0, n,
                &scale, AV_TX_UNALIGNED) < 0) {
        failed = 1;
        fftw_destroy_plan(plan);
        return NULL;
    }
    return plan;
}

void fftw_execute(const fftw_plan plan) {
    if (plan && plan->context)
        plan->execute(plan->context, plan->output, plan->input, sizeof(double));
}

void fftw_destroy_plan(fftw_plan plan) {
    if (!plan) return;
    if (plan->context && tx_uninit) tx_uninit(&plan->context);
    free(plan);
}
