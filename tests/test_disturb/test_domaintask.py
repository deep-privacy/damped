import torch
import torch.distributed as dist
from torch.multiprocessing import Process

from damped import utils
from damped import disturb


def test_domaintask_creation():
    task = disturb.DomainTask(name="speaker_identificaion", to_rank=1)
    assert task.to_rank == 1


def test_domaintask_sharetensor():
    task = disturb.DomainTask(name="speaker_identificaion", to_rank=1)

    def run(rank, size):
        if rank == task.to_rank:  # process disturb-ed
            disturb.init(port=12121)
            for _ in range(10):
                task.isend(torch.zeros(size))
                task.wait()

        else:  # Some server task running on another node
            utils.init_distributedenv(1, port=12121)

            for _ in range(10):
                recv_buff = torch.empty(  # value of (B x Tmax x D)
                    tuple(map(lambda x: int(x), size))
                )  # random value in tensor
                dist.recv(recv_buff, src=0)

                assert torch.all(torch.eq(recv_buff, torch.zeros(size)))

    processes = []
    for rank in range(2):  # fork multiple processes for testing (single machine)
        p = Process(target=run, args=(rank, (30, 300, 80)))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
