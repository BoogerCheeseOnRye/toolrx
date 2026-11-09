/* libmath.so — an "everyday DLL" callable through the tool router.
 * Compiled with:  cc -O2 -shared -fPIC -s -o native/libmath.so native/libmath.c
 */
#include <stdint.h>

int sum_ints(int *arr, int n, int mode) {
    int acc = 0;
    for (int i = 0; i < n; i++) acc += arr[i];
    return acc;
}

double average_ints(int *arr, int n) {
    if (n <= 0) return 0.0;
    return (double)sum_ints(arr, n, 0) / (double)n;
}