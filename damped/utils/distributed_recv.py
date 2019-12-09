import torch
import torch.distributed as dist
from typing import Tuple


def fork_recv(rank: int) -> Tuple[torch.Tensor, torch.Tensor]:
    """Get label and feature from forked task

    Args:
        rank (int): rank of the note in the distributed env

    Returns:
        Tuple(torch.Tensor, torch.Tensor): the related features and class label
    """
    label = recv(rank=0)
    features = recv(rank=0)
    return (features, label)


def recv(rank: int) -> torch.Tensor:
    """Receive a tensor from a DomainTask

    Args:
        rank (int): rank of the note in the distributed env

    Returns:
        torch.Tensor: data value sent
    """
    exchange_dimensions = torch.zeros(1, dtype=torch.int)  # dimensions (3)
    dist.recv(exchange_dimensions, src=rank)

    exchange_size = torch.zeros(  # shape of (B x Tmax X D)
        exchange_dimensions, dtype=torch.int
    )
    dist.recv(exchange_size, src=rank)

    recv_buff = torch.empty(  # value of (B x Tmax x D)
        tuple(map(lambda x: int(x), exchange_size.tolist()))
    )  # random value in tensor
    dist.recv(recv_buff, src=rank)
    return recv_buff
