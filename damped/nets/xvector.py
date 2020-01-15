import torch
from torch import nn

"""
The author would like to thank Anthony Larcher (https://lium.univ-lemans.fr/team/anthony-larcher/)
for sharing his xvector implementation.
"""


class Xtractor(nn.Module):
    """
    Class that defines an x-vector extractor based on 5 convolutional layers
    and a mean standard deviation pooling
    """

    def __init__(self, spk_number, dropout, eproj):
        super(Xtractor, self).__init__()
        self.frame_conv0 = nn.Conv1d(eproj, 512, 5, dilation=1)
        self.frame_conv1 = nn.Conv1d(512, 512, 3, dilation=2)
        self.frame_conv2 = nn.Conv1d(512, 512, 3, dilation=3)
        self.frame_conv3 = nn.Conv1d(512, 512, 1)
        self.frame_conv4 = nn.Conv1d(512, 3 * 512, 1)
        self.seg_lin0 = nn.Linear(3 * 512 * 2, 512)
        self.dropout_lin0 = nn.Dropout(p=dropout)
        self.seg_lin1 = nn.Linear(512, 512)
        self.dropout_lin1 = nn.Dropout(p=dropout)
        self.seg_lin2 = nn.Linear(512, spk_number)
        #
        self.norm0 = nn.BatchNorm1d(512)
        self.norm1 = nn.BatchNorm1d(512)
        self.norm2 = nn.BatchNorm1d(512)
        self.norm3 = nn.BatchNorm1d(512)
        self.norm4 = nn.BatchNorm1d(3 * 512)
        self.norm6 = nn.BatchNorm1d(512)
        self.norm7 = nn.BatchNorm1d(512)
        #
        self.activation = nn.LeakyReLU(0.2)

    def produce_embeddings(self, x):
        """

        :param x:
        :return:
        """
        frame_emb_0 = self.norm0(self.activation(self.frame_conv0(x)))
        frame_emb_1 = self.norm1(self.activation(self.frame_conv1(frame_emb_0)))
        frame_emb_2 = self.norm2(self.activation(self.frame_conv2(frame_emb_1)))
        frame_emb_3 = self.norm3(self.activation(self.frame_conv3(frame_emb_2)))
        frame_emb_4 = self.norm4(self.activation(self.frame_conv4(frame_emb_3)))

        mean = torch.mean(frame_emb_4, dim=2)
        std = torch.std(frame_emb_4, dim=2)
        seg_emb = torch.cat([mean, std], dim=1)

        embedding_a = self.seg_lin0(seg_emb)
        return embedding_a

    def forward(self, x):
        """

        :param x:
        :return:
        """
        seg_emb_0 = self.produce_embeddings(x)
        # batch-normalisation after this layer
        seg_emb_1 = self.norm6(self.activation(seg_emb_0))
        # new layer with batch Normalization
        seg_emb_2 = self.norm7(
            self.activation(self.seg_lin1(self.dropout_lin1(seg_emb_1)))
        )
        # No batch-normalisation after this layer
        result = self.activation(self.seg_lin2(seg_emb_2))
        return result

    def extract(self, x):
        """
        Extract x-vector given an input sequence of features

        :param x:
        :return:
        """
        embedding_a = self.produce_embeddings(x)
        embedding_b = self.seg_lin1(self.norm6(self.activation(embedding_a)))

        return embedding_a, embedding_b

    def init_weights(self):
        """
        Initialize the x-vector extract weights and biaises
        """
        nn.init.normal_(self.frame_conv0.weight, mean=-0.5, std=0.1)
        nn.init.normal_(self.frame_conv1.weight, mean=-0.5, std=0.1)
        nn.init.normal_(self.frame_conv2.weight, mean=-0.5, std=0.1)
        nn.init.normal_(self.frame_conv3.weight, mean=-0.5, std=0.1)
        nn.init.normal_(self.frame_conv4.weight, mean=-0.5, std=0.1)
        nn.init.xavier_uniform(self.seg_lin0.weight)
        nn.init.xavier_uniform(self.seg_lin1.weight)
        nn.init.xavier_uniform(self.seg_lin2.weight)

        nn.init.constant(self.frame_conv0.bias, 0.1)
        nn.init.constant(self.frame_conv1.bias, 0.1)
        nn.init.constant(self.frame_conv2.bias, 0.1)
        nn.init.constant(self.frame_conv3.bias, 0.1)
        nn.init.constant(self.frame_conv4.bias, 0.1)
        nn.init.constant(self.seg_lin0.bias, 0.1)
        nn.init.constant(self.seg_lin1.bias, 0.1)
        nn.init.constant(self.seg_lin2.bias, 0.1)