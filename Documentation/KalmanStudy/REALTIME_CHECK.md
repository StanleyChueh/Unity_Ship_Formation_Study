# Supplementary normal-application check

Before looking at the final v2 matrix, select one additional ON/OFF pair using
the actual asynchronous Python app.main loop and native TCP camera streaming.
Use the same adapted checkpoint, an 180 m circular leader path, two-second
scheduled bbox losses starting 20 seconds after synchronized release and repeating
every 18 seconds, and 70 seconds of motion. This checks whether the scheduled-loss
mechanism is also observable with the application's normal control cadence.

This is a descriptive external-validity check with one pair, not another set of
independent confirmatory replicates. Wall-clock startup, rendering, natural
measurement loss and network scheduling can differ between arms. Do not pool it
with the fixed-step matrix or claim exact matched observations. Use the existing
application metrics and matching JPEG/identity-mask samples. Keyboard axis reads
are neutralized only in the isolated copy, as in v2.

The normal app's three-boat RMS/equilateral target definition differs from the
primary matrix's follower-only RMSE and initial-offset target. Report both with
their definitions rather than numerically merging them.
