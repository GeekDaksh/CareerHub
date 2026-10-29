#!/bin/bash
# Fetch EMSCAD (Vidros et al., 2017; 17,880 real job ads, 866 fraudulent) from a public GitHub mirror and pin its hash.
set -e
DEST="${1:-eval/.data}"
mkdir -p "$DEST"
if [ ! -f "$DEST/fake_job_postings.csv" ]; then
  tmp=$(mktemp -d)
  GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 https://github.com/FelixLuciano/Fake-JobPosting-Prediction "$tmp/r"
  cp "$tmp/r/src/dataset/fake_job_postings.csv" "$DEST/"
  rm -rf "$tmp"
fi
echo "874aea73d6fb9e35ed48846991e652cdedfc4c3dcbd839a7ba9770f61391c8ba  $DEST/fake_job_postings.csv" | sha256sum -c -
