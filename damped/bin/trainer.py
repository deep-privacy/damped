#!/usr/bin/env python3

import torch
import damped
from damped import utils
from damped.disturb import const
from sklearn.metrics import accuracy_score
import kaldiio

import configargparse
import importlib.util
import os
import time


def str_to_bool(value):
    if value.lower() in {'false', 'f', '0', 'no', 'n'}:
        return False
    elif value.lower() in {'true', 't', '1', 'yes', 'y'}:
        return True
    raise ValueError(f'{value} is not a valid boolean value')


def get_parser(parser=None):
    """Get default arguments."""
    if parser is None:
        parser = configargparse.ArgumentParser(description="Eval an domain branch")

    parser.add("--config", type=str, help="config file path", required=True)
    parser.add(
        "--log-interval",
        type=int,
        help="Log training accuracy every X batch",
        nargs="?",
        required=False,
        default=10,
    )
    parser.add(
        "--exp-path",
        help="Path to save the exp model/results",
        required=True,
        type=str,
    )
    parser.add(
        "--task-rank",
        type=int,
        help="The rank of this task (torch.distributed)",
        required=True,
    )
    parser.add(
        "--n-checkpoint",
        type=int,
        help="The number of checkpoints to keep (checkpoint frequency defined by log-interval)",
        nargs="?",
        required=False,
        default=5,
    )
    parser.add(
        "--gpu-device",
        help="If the node has GPU accelerator, select the GPU to use",
        nargs="?",
        required=False,
        type=int,
        default=0,
    )
    parser.add(
        "--resume",
        help="Resume the training from a checkpoint",
        default="",
        nargs="?",
        required=False,
        type=str,
    )
    parser.add(
        "--world-size",
        help="The number of expected TOTAL domain task (might be more than one)",
        required=True,
        type=int,
    )
    parser.add(
        "--master-ip",
        help="The ipv4 or ipv6 address of the master node. (The one that was damped.disturb-ed)",
        required=True,
        type=str,
    )
    parser.add(
        "--tensorboard-dir",
        help="Tensorboard log dir path",
        default="",
        nargs="?",
        required=False,
        type=str,
    )
    parser.add(
        "--load-optimizer",
        help="when a model is --resume, also load the optimizer",
        default=True,
        nargs="?",
        required=False,
        type=str_to_bool,
    )
    parser.add(
        "--train-mode",
        help="train_mode [train, trainstore, finetune, ignore]",
        default="train",
        nargs="?",
        required=False,
        type=str,
    )

    return parser


def main():
    """Run the main training function."""
    parser = get_parser()
    args, _ = parser.parse_known_args()

    print("Train mode:", args.train_mode, flush=True)

    device = torch.device(
        f"cuda:{args.gpu_device}" if torch.cuda.is_available() else "cpu"
    )

    # load the conf
    spec = importlib.util.spec_from_file_location("config", args.config)
    config = importlib.util.module_from_spec(spec)
    config.argsparser = (
        parser  # Share the configargparse.ArgumentParser with the user defined module
    )
    spec.loader.exec_module(config)

    # create the net and training optim/criterion
    optimizer = config.optimizer
    net = config.net.to(device)
    criterion = config.criterion

    # keep track of some values while training
    total_correct = 0
    total_target = 0

    tensorboard_dir = args.tensorboard_dir
    if args.tensorboard_dir == "":
        tensorboard_dir = os.path.join("exp/", args.exp_path, "tensorboard")

    monitor = utils.Monitor(
        tensorboard_dir=tensorboard_dir,
        save_path=os.path.join("exp/", args.exp_path),
        exp_id=net.__class__.__name__,
        model=net,
        eval_metrics="acc, loss",
        early_metric="acc",
        save_best_metrics=True,
        n_checkpoints=args.n_checkpoint,
    )
    monitor.set_optimizer(optimizer)
    monitor.save_model_summary()

    if args.resume:
        print("resumed from %s" % args.resume, flush=True)
        # load last checkpoint
        monitor.load_checkpoint(args.resume, args.load_optimizer)

    # Eval related
    eval_mode = False
    total_labels = torch.LongTensor([])
    total_pred = torch.LongTensor([])
    loss_batches = 0
    loss_batches_count = 0

    # indicate if damped.disturb-ed toolkit wants the gradient form the DomainTask
    send_backward_grad = False

    # init the rank of this task
    if args.train_mode != "finetune":
        utils.init_distributedenv(
            rank=args.task_rank, world_size=args.world_size, ip=args.master_ip
        )

    print("Training started on %s" % time.strftime("%d-%m-%Y %H:%M"), flush=True)

    # TODO(pchampio) refactor this training loop into sub-functions
    i = 0
    world = list(range(1, args.world_size))
    has_performd_backward = False
    train_store = None
    eval_store = None
    if args.train_mode == "finetune":
        print("NOT IMPLEMENTED!", flush=True)
        quit(1)
        #  f = os.path.join(monitor.save_path, ("trainstore.pt"))
        #  train_store = torch.load(f)
        #  f = os.path.join(monitor.save_path, ("evalstore.pt"))
        #  eval_store = torch.load(f)

    while True:
        i+=1

        domain_task_id_index = i % len(world)
        domain_task_id = world[domain_task_id_index]

        if args.train_mode == "finetune":

            is_meta_data = False
            features = train_store["features"][(i-1) % len(train_store["features"])]
            y_mapper = train_store["target"][(i-1) % len(train_store["target"])]

        else:
            if args.task_rank == 0:
                features, y_mapper, is_meta_data = utils.fork_recv(
                    rank=domain_task_id, dtype=(torch.float32, torch.long)
                )

            else:
                features, y_mapper, is_meta_data = utils.fork_recv(
                    rank=0, dtype=(torch.float32, torch.long)
                )

        if is_meta_data:
            meta_data = y_mapper

            if const.should_stop(meta_data):
                print(f"worker: {domain_task_id} stopped", flush=True)
                world.pop(domain_task_id_index)
                if len(world) == 0:
                    monitor.save_models()
                    break

            if const.is_no_wait_backward(meta_data):
                print("Switch to NOT sending backward gradient", flush=True)
                send_backward_grad = False

            if const.is_wait_backward(meta_data):
                print("Switch to sending backward gradient", flush=True)
                send_backward_grad = True

            last_eval = eval_mode
            eval_mode = const.is_eval(meta_data)

            # detect changes from train to eval
            if eval_mode and not last_eval:
                print("Running evaluation on dev..", flush=True)
                net.eval()

            # detect changes from eval to train
            if not eval_mode and last_eval:
                net.train()
                # display validation metics
                accuracy = (
                    accuracy_score(
                        total_labels.flatten().numpy(), total_pred.flatten().numpy()
                    )
                    * 100
                )

                loss = 0
                if loss_batches_count != 0:
                    loss = loss_batches / loss_batches_count

                monitor.update_dev_scores(
                    [
                        utils.Metric("acc", accuracy),
                        utils.Metric("loss", loss, higher_better=False,),
                    ]
                )

                if not has_performd_backward:
                    monitor.vctr -= 1

                monitor.save_models()

                if not has_performd_backward: # pkwrap case where valid is a new iteration (must use previous one)
                    monitor.vctr +=1
                monitor.vctr += 1
                # clear for next eval
                total_labels = torch.LongTensor([])
                total_pred = torch.LongTensor([])
                loss_batches = 0
                loss_batches_count = 0

            # When meta_data is shared, no features/label are sent
            continue

        if args.train_mode == "ignore":
            continue


        target = config.mapper(y_mapper)

        input = features.to(device)
        input.requires_grad = True

        if args.train_mode == "trainstore" and not eval_mode:
            for f, t in zip(features.cpu().numpy(), config.mapper(y_mapper, raw=True)):
                kaldiio.save_ark(os.path.join(monitor.save_path, ("train_store.ark")), {f'spk_id_{t}': f}, append=True, compression_method=1, scp=os.path.join(monitor.save_path, ("train_store.scp")))

        # Eval
        if eval_mode:
            for f, t in zip(features.cpu().numpy(), config.mapper(y_mapper, raw=True)):
                kaldiio.save_ark(os.path.join(monitor.save_path, ("eval_store.ark")), {f'spk_id_{t}': f}, append=True, compression_method=1, scp=os.path.join(monitor.save_path, ("eval_store.scp")))

            y_pred = net(input)

            # send back the gradient if needed
            if send_backward_grad:
                # backward will not be applied (eval), send 0 grad
                damped.disturb.DomainTask._isend(0, torch.zeros(*input.size())).wait()

            _, predicted = torch.max(y_pred.data, dim=1)

            total_labels = torch.cat((total_labels, target.cpu()))
            total_pred = torch.cat((total_pred, predicted.cpu()))

            loss = criterion(y_pred, target.to(device))

            loss_batches += loss.cpu().detach().numpy()
            loss_batches_count += 1
            continue

        optimizer.zero_grad()
        y_pred = net(input)

        if torch.any(torch.isnan(y_pred)):
            print(features)
            print("ERROR: ignoring this batch, prediction is NaN")
            continue

        loss = criterion(y_pred, target.to(device))
        loss.backward()
        has_performd_backward = True

        # send back the gradient if asked
        if send_backward_grad:
            damped.disturb.DomainTask._isend(0, input.grad.data.cpu()).wait()

        optimizer.step()

        correct = (torch.argmax(y_pred.data, 1) == target.to(device)).sum().item()
        total_correct += correct
        total_target += target.size(0)

        monitor.train_loss.append(loss.item())

        monitor.uctr += 1
        if monitor.uctr % args.log_interval == 0:
            accuracy = (total_correct / total_target) * 100
            print(
                "Train batch [{}]\tLoss: {:.6f}\tTrain Accuracy: {:.3f}".format(
                    monitor.uctr, loss.item(), accuracy,
                ),
                flush=True,
            )
            monitor.tensorboard_writter.add_scalar(
                "/train/accuracy", accuracy, monitor.uctr
            )
            monitor.tensorboard_writter.add_scalar(
                "/train/loss", loss.item(), monitor.uctr
            )
            total_correct = 0
            total_target = 0

    print("Training finished on %s" % time.strftime("%d-%m-%Y %H:%M"))


if __name__ == "__main__":
    main()
