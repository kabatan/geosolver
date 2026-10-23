/* Constants are taken from this platform's fenv.h, never guessed. */
#include <fenv.h>
#pragma STDC FENV_ACCESS ON
int q34_get(void) { return fegetround(); }
int q34_set(int value) { return fesetround(value); }
int q34_constant(int which) {
    return which == 1 ? FE_DOWNWARD : which == 2 ? FE_UPWARD : FE_TONEAREST;
}
