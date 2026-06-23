VALUES = {
    "whole":             1.0,
    "half":              0.5,
    "quarter":           0.25,
    "eighth":            0.125,
    "sixteenth":         0.0625,
    "thirty_second":     0.03125,
    "dotted_whole":      1.5,
    "dotted_half":       0.75,
    "dotted_quarter":    0.375,
    "dotted_eighth":     0.1875,
    "dotted_sixteenth":  0.09375,
    "dotted_thirty_second": 0.046875,
}

def get_value(ntype):
    return VALUES[ntype]
