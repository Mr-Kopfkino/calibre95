/* Test-only ABI, built separately from the shipped DLL. */
#include "fftw3.h"
#include <string.h>
__declspec(dllexport) int check_r2c(const double *input, int n, double *output) {
    double *in = fftw_alloc_real(n);
    fftw_complex *out = fftw_alloc_complex(n / 2 + 1);
    fftw_plan p = fftw_plan_dft_r2c_1d(n, in, out, FFTW_ESTIMATE);
    if (!p) { fftw_free(in); fftw_free(out); return -1; }
    memcpy(in, input, n * sizeof(double));
    fftw_execute(p);
    memcpy(output, out, (n / 2 + 1) * sizeof(fftw_complex));
    fftw_destroy_plan(p); fftw_free(in); fftw_free(out);
    return 0;
}
