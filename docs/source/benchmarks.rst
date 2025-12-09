.. _benchmarks:

#########################
Benchmarks & Overhead
#########################

Runtime Overhead:
*   Decorator overhead: ~0.8–1.2 μs per call
*   Trace flush: background + negligible
*   No heavy memory sampling
*   Suitable for production with sampling rate control