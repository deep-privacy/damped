#!/usr/bin/env python

import os
import sys
from damped import nets
from damped.utils import gender_mapper
import torch
import torch.nn as nn
import configargparse

device = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")

# This file will be used to define the domain branch.

# The folowing variable MUST be defined, it will be imported by trainer.py!
# - `net` for the network architecture
# - `criterion` for the loss
# - `optimizer`
# - `mapper` to map the distirb y label to the domain task y label

parser = configargparse.ArgumentParser()
parser.add("--tdnn-in", dest="tdnn_in", type=int, default=1024)
args = parser.parse_args()


# Assuming 1024 dim per frame (T)
frame1 = nets.TDNN(input_dim=args.tdnn_in, output_dim=512, context_size=5, dilation=1)
frame2 = nets.TDNN(input_dim=512, output_dim=512, context_size=3, dilation=2)
frame3 = nets.TDNN(input_dim=512, output_dim=512, context_size=3, dilation=3)
frame4 = nets.TDNN(input_dim=512, output_dim=512, context_size=1, dilation=1)
frame5 = nets.TDNN(input_dim=512, output_dim=1500, context_size=1, dilation=1)
# Input to frame1 is of shape (batch_size, T, 24)
# Output of frame5 will be (batch_size, T-14, 1500)

print(sys.argv[1:])

net = nn.Sequential(
    frame1,
    frame2,
    frame3,
    frame4,
    frame5,
    nets.StatsPooling(),  # mean + std (out_dim = 2x in_dim = 3000) over frame5
    nets.DenseEmbedding(in_dim=3000, mid_dim=512, out_dim=512),
    nets.DenseReLU(512, 2),
    nn.Softmax(dim=1),
).to(device)

#  Binary Cross Entropy
criterion = nn.BCELoss(reduction="mean")

# Optim
optimizer = torch.optim.Adam(net.parameters())

# mapper used for ../data/spk2gender
dir_path = os.path.dirname(os.path.realpath(__file__))
mapper = gender_mapper(dir_path)