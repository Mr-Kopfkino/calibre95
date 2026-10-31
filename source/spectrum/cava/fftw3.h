/* calibre95: the small FFTW API subset used by cavacore, backed by FFmpeg.
 * This is original adapter code, not an FFTW implementation or FFTW source.
 * GPL-3.0-or-later; original CAVA source retains its MIT license.
 */
#ifndef C95_FFTW_ADAPTER_H
#define C95_FFTW_ADAPTER_H
#include <stddef.h>
#include <stdio.h>
typedef double fftw_complex[2];
typedef struct c95_fft_plan *fftw_plan;
#define FFTW_MEASURE 0
#define FFTW_ESTIMATE 64
double *fftw_alloc_real(size_t n);
fftw_complex *fftw_alloc_complex(size_t n);
fftw_plan fftw_plan_dft_r2c_1d(int n, double *input, fftw_complex *output, unsigned flags);
void fftw_execute(const fftw_plan plan);
void fftw_destroy_plan(fftw_plan plan);
void fftw_free(void *ptr);
int c95_fft_available(void);
int c95_fft_failed(void);
#endif
