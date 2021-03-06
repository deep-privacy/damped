#!/bin/bash

# Generate spkid file based on the 'train-.*' subset!

dst=./data

mkdir -p $dst

spk_file=./download/LibriSpeech/SPEAKERS.TXT

spk2id=$dst/spk2id; [[ -f $spk2id ]] && rm $spk2id

grep "^^[0-9]*\s+\|.*$1" -E  download/LibriSpeech/SPEAKERS.TXT | awk -F'|' '{gsub(/[ ]+/, ""); print $1, NR-1}' > $spk2id

echo "$0 spk2id file created (filter: $1)"
