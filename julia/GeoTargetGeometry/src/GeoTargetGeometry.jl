module GeoTargetGeometry

using GeoTargetBase

"""Return the ABI version implemented by the built-in geometry plugin."""
abi_version() = GeoTargetBase.PACKAGE_VERSION

export abi_version

end

