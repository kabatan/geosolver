from functools import partial
from typing import Any, Callable, List

from .local_optimizer import OptimizationResult


class HighPrecisionRefiner:
    """mpmathを使用した高精度リファインメント"""

    def refine(
        self,
        f: Callable[[List[Any]], List[Any]],
        x0: List[float],
        precision: int = 30,
    ) -> OptimizationResult:
        """
        初期値 x0 から mpmath.findroot で高精度解を探索する。
        """
        from mpmath import mp, findroot, norm
        from geosolver.geometry import use_runtime, BackendType

        dps = precision + 5

        with use_runtime(BackendType.MPMATH, precision=dps):
            old_dps = mp.dps
            mp.dps = dps

            try:
                x0_mp = [mp.mpf(val) for val in x0]
                f_wrapper = partial(_high_precision_findroot_wrapper, residual_function=f)

                try:
                    res_x = findroot(f_wrapper, x0_mp, solver="mdnewton", tol=10 ** (-precision))
                except Exception:
                    raise

                if hasattr(res_x, "tolist"):
                    res_x_list = [x[0] for x in res_x.tolist()]
                elif isinstance(res_x, (list, tuple)):
                    res_x_list = list(res_x)
                else:
                    res_x_list = [res_x]

                residuals = f(res_x_list)
                res_norm = float(norm(residuals, 2))

                return OptimizationResult(
                    x=res_x_list,
                    fun=res_norm,
                    success=res_norm < 10 ** (-precision + 2),
                    message="High precision refinement successful",
                )

            except Exception as e:
                mp.dps = old_dps
                return OptimizationResult(
                    x=x0,
                    fun=float("inf"),
                    success=False,
                    message=f"Refinement failed: {str(e)}",
                )
            finally:
                mp.dps = old_dps


def _high_precision_findroot_wrapper(
    *args: Any,
    residual_function: Callable[[List[Any]], List[Any]],
) -> List[Any]:
    return residual_function(list(args))