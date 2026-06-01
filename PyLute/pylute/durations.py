VALUES = {
    "whole":          1.0,
    "half":           0.5,
    "quarter":        0.25,
    "eighth":         0.125,
    "sixteenth":      0.0625,
    "dotted_half":    0.75,
    "dotted_quarter": 0.375,
    "dotted_eighth":  0.1875,
}

def get_value(ntype):
    return VALUES[ntype]
