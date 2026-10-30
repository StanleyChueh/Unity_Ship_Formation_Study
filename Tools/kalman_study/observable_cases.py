"""Additional development cases proposed after observing legacy visibility failure.

These are not part of the frozen original matrix and have not been run. They
remove continuous rain from C5/C6 while preserving motion, waves and scheduled
losses, so temporary prediction can be evaluated while the target is observable
between events. Import explicitly into a NEW tagged runner/protocol.
"""
OBSERVABLE_CASES = [
    dict(case='C8_clear_speed_s_dropout',sea=1.0,rain=0,dark=False,fog=0,motion='variable',radius=360,gap=2.0),
    dict(case='C9_clear_rough_brief_dropout',sea=1.2,rain=0,dark=False,fog=0,motion='circle',radius=220,gap=0.5),
]
