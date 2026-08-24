from .radical_inverse import _radical_inverse

def _halton_value(sample_index: int, base: int) -> float:
    """Get the nth value of the Halton sequence for a given base.
    
    Conventionally start from index>=1 to avoid zeros.
    """
    return _radical_inverse(sample_index, base)
