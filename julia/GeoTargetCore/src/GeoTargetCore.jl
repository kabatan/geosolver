module GeoTargetCore

using GeoTargetBase

"""Return the ABI version understood by this Core build."""
abi_version() = GeoTargetBase.PACKAGE_VERSION

export abi_version

end

