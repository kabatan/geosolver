# Optional native geometry kernel

This crate is an experimental PyO3 arm for effect-certified flat tapes. It is
not part of the default Hatch build unless the native arm passes the complete
performance gate.

The kernel rejects signed zero, subnormal and non-finite inputs or
intermediates, periodic operations, selectors, and every opcode outside its
explicit allowlist. Rejection returns control to the complete Python flat-tape
callback; native results are never mixed with a partially evaluated Python
callback.

Build into an external staging directory without modifying `src/`:

```console
uv run --with maturin==1.10.2 python native-kernel/build_stage.py \
  /absolute/artifact/directory
```

The staging script emits a wheel, the extracted extension, and a SHA-256
sidecar. Set `GEOTARGET_NATIVE_MODULE_PATH` to the staged extension for arm
qualification. Production wheels do not use that environment variable.
