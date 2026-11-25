# Video regression fixture

`vfr-test-pattern.mp4` is a 64×48 synthetic FFmpeg test pattern, generated locally
with FFmpeg 8.0.1 and libx264. It contains no uploaded or third-party footage.
It has ten frames at presentation times 0, .1, .2, .3, .4, .5, 1, 1.5, 2, 2.5 seconds.
It tests variable-frame-rate decoding; it is not model-quality acceptance data.

Reproduce:

```sh
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=64x48:rate=10:duration=1 \
  -vf "setpts='if(lt(N,5),N/(10*TB),(0.5+(N-5)/2)/TB)'" \
  -fps_mode vfr -c:v libx264 -pix_fmt yuv420p vfr-test-pattern.mp4
```
