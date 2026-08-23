import { useEffect, useReducer } from "react";

export type LayoutSizes = { left: number; right: number; bottom: number };
export const DEFAULT_LAYOUT_SIZES: LayoutSizes = {
  left: 288,
  right: 360,
  bottom: 280,
};
export const LAYOUT_STORAGE_KEY = "geosolver.layout.v1";
export const INSPECTOR_DRAWER_MIN_WIDTH = 768;
export const DESKTOP_MODEL_PANE_MIN_WIDTH = 1100;
export const WIDE_WORKBENCH_MIN_WIDTH = 1440;

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function loadSizes(): LayoutSizes {
  if (typeof window === "undefined") return DEFAULT_LAYOUT_SIZES;
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(LAYOUT_STORAGE_KEY) ?? "null",
    ) as Partial<LayoutSizes> | null;
    return {
      left: clamp(Number(stored?.left) || DEFAULT_LAYOUT_SIZES.left, 250, 520),
      right: clamp(Number(stored?.right) || DEFAULT_LAYOUT_SIZES.right, 270, 520),
      bottom: clamp(Number(stored?.bottom) || DEFAULT_LAYOUT_SIZES.bottom, 150, 420),
    };
  } catch {
    return DEFAULT_LAYOUT_SIZES;
  }
}

type State = {
  sizes: LayoutSizes;
  viewportWidth: number;
  drawerOpen: boolean;
};
type Action =
  | { type: "resize"; viewportWidth: number }
  | { type: "size"; pane: keyof LayoutSizes; value: number }
  | { type: "drawer"; open: boolean };

function reducer(state: State, action: Action): State {
  if (action.type === "drawer") return { ...state, drawerOpen: action.open };
  if (action.type === "size")
    return { ...state, sizes: { ...state.sizes, [action.pane]: action.value } };
  let sizes = state.sizes;
  if (action.viewportWidth >= WIDE_WORKBENCH_MIN_WIDTH) {
    const panelBudget = Math.max(520, action.viewportWidth - 14 - 280);
    let left = clamp(sizes.left, 250, 520);
    let right = clamp(sizes.right, 270, 520);
    const excess = left + right - panelBudget;
    if (excess > 0) {
      const reduceLeft = Math.min(excess, left - 250);
      left -= reduceLeft;
      right -= Math.min(excess - reduceLeft, right - 270);
    }
    sizes = { ...sizes, left, right };
  }
  return {
    sizes,
    viewportWidth: action.viewportWidth,
    drawerOpen:
      action.viewportWidth >= INSPECTOR_DRAWER_MIN_WIDTH &&
      action.viewportWidth < WIDE_WORKBENCH_MIN_WIDTH
        ? state.drawerOpen
        : false,
  };
}

export function useWorkbenchLayout() {
  const [state, dispatch] = useReducer(reducer, undefined, () => ({
    sizes: loadSizes(),
    viewportWidth: typeof window === "undefined" ? 1440 : window.innerWidth,
    drawerOpen: false,
  }));

  useEffect(() => {
    window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(state.sizes));
  }, [state.sizes]);

  useEffect(() => {
    const resize = () =>
      dispatch({ type: "resize", viewportWidth: window.innerWidth });
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  return {
    sizes: state.sizes,
    viewportWidth: state.viewportWidth,
    drawerOpen: state.drawerOpen,
    setSize: (pane: keyof LayoutSizes, value: number) =>
      dispatch({ type: "size", pane, value }),
    setDrawerOpen: (open: boolean) => dispatch({ type: "drawer", open }),
  };
}
