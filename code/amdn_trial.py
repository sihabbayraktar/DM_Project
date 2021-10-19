import dpp
from dpp.data import Batch
import os, sys
import numpy as np
import torch
import torch.nn as nn
import torch.distributions as td
from copy import deepcopy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
# import seaborn as sns
# torch.set_default_tensor_type(torch.cuda.FloatTensor)
import argparse
import sys
import pickle as pkl
# %load_ext autoreload
# %autoreload 2

import pandas as pd


def load_data(args):
  split = 'train'
  file_name = sampling(args, split);
  data = pkl.load(open(os.path.join(args.data_dir, f'{args.data_prefix}_{split}{file_name}'), 'rb'))
  
  seq = dpp.data.load_dataset_from_split(data, split, log_mode=True)
  num_classes = data['dim_process'] if 'marks' in data[split] is not None else 1
  num_sequences = len(data[split]['arrival_times'])
  d_train, d_val, d_test = seq.train_val_test_split_each(0.6, 0.2, 0.2)

  mean_in_train, std_in_train = d_train.get_mean_std_in(); std_out_train = 1.0
  d_train.normalize(mean_in_train, std_in_train, std_out_train)
  d_val.normalize(mean_in_train, std_in_train, std_out_train)
  d_test.normalize(mean_in_train, std_in_train, std_out_train)
  logging.info('Mean and std in train = {} and {}'.format(mean_in_train, std_in_train))
  if np.isinf(mean_in_train) or np.isinf(std_in_train):
    logging.info('Something is negative or 0 when taking log on delta_times (difference in times)')
    sys.exit()
  if np.isnan(mean_in_train) or np.isnan(std_in_train):
    logging.info('Something is negative or 0 when taking log on delta_times (difference in times)')
    sys.exit()

  # for padding input sequences to maxlen of batch for running on gpu, and arranging them by length efficient
  collate = dpp.data.collate  
  dl_train = torch.utils.data.DataLoader(d_train, batch_size=args.batch_size, shuffle=False, collate_fn=collate)
  dl_val = torch.utils.data.DataLoader(d_val, batch_size=args.batch_size, shuffle=False, collate_fn=collate)
  dl_test = torch.utils.data.DataLoader(d_test, batch_size=args.batch_size, shuffle=False, collate_fn=collate)

  # Set the parameters for affine normalization layer depending on the decoder 
  # (see Appendix D.3 in the paper - like batch normalization)
  if args.decoder_name in ['RMTPP', 'FullyNeuralNet', 'Exponential']:
    _, std_out_train = d_train.get_mean_std_out()
    mean_out_train = 0.0
  else: 
    mean_out_train, std_out_train = d_train.get_log_mean_std_out()
    logging.info('Mean and std out train = {} and {}'.format(mean_out_train, std_out_train))
    
    return dl_train, dl_val, dl_test, mean_out_train, std_out_train, num_classes, num_sequences


def sampling(args, split):
  data = pd.read_pickle(str(args.data_dir) + f'{args.data_prefix}_{split}.pkl')
  data_frame = data_frame=pd.DataFrame.from_dict(data[split], orient='columns')
  data_sample = pd.DataFrame(data_frame.sample(frac=0.25))


  ##HARDCODED
  new_data = {'dim_process' : data['dim_process'], 'devtest': data['devtest'],
            'args': data['args'], 'train': data_sample.to_dict('list'), 'dev': data['dev'],
            'test': data['test'], 'index':data['index']}


  new_path = args.data_dir + args.data_prefix + "_" + "train" +  "_sampling.pkl"
  pkl.dump(new_data, open(new_path, "wb"))
  
  return "_sampling.pkl"  

"""    
def load_data(args):
    ### Data (normalize input inter-event times, then padding to create dataloaders)
    num_classes, num_sequences = 0, 0
    seq_dataset = []
    for split in ['train', 'dev', 'test']:
        data = pkl.load(open(os.path.join(args.data_dir, f'{args.data_prefix}_{split}.pkl'), 'rb'))
        logging.info(f'loaded split {split}...')
        # data - dict: dim_process, devtest, args, train, dev, test, index (train/dev/test given as)
        # data[split] - list dicts {'time_since_start': at, 'time_since_last_event': dt, 'type_event': mark} or
        # data[split] - dict {'arrival_times', 'delta_times', 'marks'}
        num_classes = data['dim_process'] if 'marks' in data[split] is not None else 1
        num_sequences += len(data[split]['arrival_times'])
        seq_dataset.append(dpp.data.load_dataset_from_split(data, split, log_mode=True)) # SequenceDataset
    d_train, d_val, d_test = seq_dataset
    # Standardize input inter-event times: 
    # calc mean and std of the input inter-event times and normalize only input times
    # Transformed data to centered around 0 mean and stddev of 1
    mean_in_train, std_in_train = d_train.get_mean_std_in(); std_out_train = 1.0
    d_train.normalize(mean_in_train, std_in_train, std_out_train)
    d_val.normalize(mean_in_train, std_in_train, std_out_train)
    d_test.normalize(mean_in_train, std_in_train, std_out_train)
    logging.info('Mean and std in train = {} and {}'.format(mean_in_train, std_in_train))
    if np.isinf(mean_in_train) or np.isinf(std_in_train):
        logging.info('Something is negative or 0 when taking log on delta_times (difference in times)')
        sys.exit()
    if np.isnan(mean_in_train) or np.isnan(std_in_train):
        logging.info('Something is negative or 0 when taking log on delta_times (difference in times)')
        sys.exit()

    # for padding input sequences to maxlen of batch for running on gpu, and arranging them by length efficient
    collate = dpp.data.collate  
    dl_train = torch.utils.data.DataLoader(d_train, batch_size=args.batch_size, shuffle=False, collate_fn=collate)
    dl_val = torch.utils.data.DataLoader(d_val, batch_size=args.val_batch_size, shuffle=False, collate_fn=collate)
    dl_test = torch.utils.data.DataLoader(d_test, batch_size=args.val_batch_size, shuffle=False, collate_fn=collate)

    # Set the parameters for affine normalization layer depending on the decoder 
    # (see Appendix D.3 in the paper - like batch normalization)
    if args.decoder_name in ['RMTPP', 'FullyNeuralNet', 'Exponential']:
        _, std_out_train = d_train.get_mean_std_out()
        mean_out_train = 0.0
    else: 
        mean_out_train, std_out_train = d_train.get_log_mean_std_out()
    logging.info('Mean and std out train = {} and {}'.format(mean_out_train, std_out_train))
    
    return dl_train, dl_val, dl_test, mean_out_train, std_out_train, num_classes, num_sequences
"""
def create_model(num_classes, num_sequences, args, mean_out_train, std_out_train):
    # General model config
    general_config = dpp.model.ModelConfig(
        encoder_type=args.encoder_type, use_history=args.use_history, history_size=args.history_size, rnn_type=args.rnn_type,
        use_embedding=args.use_embedding, embedding_size=args.embedding_size, num_embeddings=num_sequences, # seq emb
        use_marks=args.use_marks, mark_embedding_size=args.mark_embedding_size, num_classes=num_classes,
        heads=args.heads, depth=args.depth, wide=args.wide, seq_length=args.max_seq_length, device=args.device,
        pos_enc=args.pos_enc, add=args.add, time_opt=args.time_opt, expand_dim=args.expand_dim,
    )
                    
    # Decoder specific config
    decoder = getattr(dpp.decoders, args.decoder_name)(general_config, n_components=args.n_components,
                                                  hypernet_hidden_sizes=args.hypernet_hidden_sizes,
                                                  max_degree=args.max_degree, n_terms=args.n_terms,
                                                  n_layers=args.n_layers, layer_size=args.layer_size,
                                                  shift_init=mean_out_train, scale_init=std_out_train,
                                                  trainable_affine=args.trainable_affine)
    model = dpp.model.Model(general_config, decoder).to(args.device)
    # model = nn.DataParallel(dpp.model.Model(general_config, decoder)).to(args.device)
    
    logging.info(model)
    opt = torch.optim.Adam(model.parameters(), weight_decay=args.regularization, lr=args.learning_rate)
    
    # for name, param in model.named_parameters():
    #    logging.info(name, param.device)
    
    return model, opt


def move_input_batch_to_device(input, device):
    input_device = Batch(input.in_time.to(device), input.out_time.to(device),
                         input.length.to(device), input.index.to(device), 
                         input.in_mark.to(device), input.out_mark.to(device))
    return input_device
    
    
def get_total_loss(loader, model, use_marks, device):
    loader_loss, loader_lengths = [], []; 
    loader_time_nll, loader_mark_nll, loader_acc = [], [], [];
    for input in loader:
        input = move_input_batch_to_device(input, device)
        if use_marks:
            log_prob, mark_nll, accuracy = model.log_prob(input)
            loader_loss.append(log_prob.detach() - mark_nll.detach())
            loader_time_nll.append(-log_prob.detach())
            loader_mark_nll.append(mark_nll.detach()); loader_acc.append(accuracy.detach())
            del log_prob, mark_nll, accuracy
        else:
            loader_loss.append(model.log_prob(input).detach())     
        loader_lengths.append(input.length.detach())
    total_loss = -model.aggregate(loader_loss, loader_lengths, device).item()  # -LL
    time_loss, marks_loss, acc_val = None, None, None
    if use_marks:
        time_loss = model.aggregate(loader_time_nll, loader_lengths, device).item() # NLL 
        marks_loss = model.aggregate(loader_mark_nll, loader_lengths, device).item() # NLL
        acc_val = model.aggregate(loader_acc, loader_lengths, device).item() # NLL
    return total_loss, time_loss, marks_loss, acc_val


def train(model, opt, dl_train, dl_val, logging, use_marks, 
          max_epochs, patience, display_step, save_freq, out_dir, device):
    # Training (max_epochs or until the early stopping condition is satisfied)
    # Function that calculates the loss for the entire dataloader
    impatient = 0
    best_loss = np.inf
    best_model = deepcopy(model.state_dict())
    plot_val_losses = []
    
    for epoch in range(max_epochs):
        # Train epoch
        model.train()
        for input in dl_train:
            input = move_input_batch_to_device(input, device)
            opt.zero_grad()
            if use_marks:
                log_prob, mark_nll, accuracy = model.log_prob(input)
                loss = -model.aggregate(log_prob, input.length, device) + model.aggregate(
                    mark_nll, input.length, device)
                del log_prob, mark_nll, accuracy
            else:
                loss = -model.aggregate(model.log_prob(input), input.length, device)
            loss.backward()
            opt.step()
        # End of Train epoch

        model.eval()  # val losses over all val batches aggregated
        loss_val, loss_val_time, loss_val_marks, loss_val_acc = get_total_loss(
            dl_val, model, use_marks, device) 
        plot_val_losses.append([loss_val, loss_val_time, loss_val_marks, loss_val_acc])

        if (best_loss - loss_val) < 1e-4:
            impatient += 1
            if loss_val < best_loss:
                best_loss = loss_val
                best_model = deepcopy(model.state_dict())
        else:
            best_loss = loss_val
            best_model = deepcopy(model.state_dict())
            impatient = 0

        if impatient >= patience:
            logging.info(f'Breaking due to early stopping at epoch {epoch}'); break

        if (epoch + 1) % display_step == 0:
            logging.info(f"Epoch {epoch+1:4d}, trlast = {loss:.4f}, val = {loss_val:.4f}")
        if (epoch + 1) % save_freq == 0:
            torch.save(best_model, os.path.join(out_dir, 'best_model_state_dict_ep_{}.pt'.format(epoch)))
            # evaluate(model, [dl_train, dl_val], ['Ckpt_train', 'Ckpt_val'], use_marks, device)
            logging.info(f"saved intermediate checkpoint")

    logging.info('Training finished.............')
    torch.save(best_model, os.path.join(out_dir, 'best_model_state_dict.pt'))
    model.load_state_dict(best_model)
    torch.save(model, os.path.join(out_dir, 'best_full_model.pt'))
    logging.info(f"The entire model is saved in {os.path.join(out_dir, 'best_full_model.pt')}.")    
    # loading model model = torch.load(save_model_path)
    
    # Plot training curve displaying separated validation losses
    plot_loss = np.array(plot_val_losses)
    if len(plot_loss) > patience:
        plot_loss = plot_loss[:-patience] # plot only until early stopping
    fig, axes = plt.subplots(1, 4, figsize=(20, 4))
    plot_labels = ['Total_loss', 'Time_NLL', 'Marks_NLL', 'Marks_Acc']
    for i in range(plot_loss.shape[1]):
        ax = axes[i]
        ax.plot(range(len(plot_loss)), plot_loss[:, i], marker='o', label=plot_labels[i], markersize=3)
        ax.set_xlabel('Val Loss vs. Training Epoch')
        # ax.set_ylabel(plot_labels[i])
        # ax.set_title('Validation dataset')
        ax.legend()
    plt.savefig(os.path.join(out_dir, 'training_curve.png'))
    
    
def extract_features(model, logging, args):
    model.eval()
    ## mark embeddings
    z = model.rnn.mark_embedding.weight.cpu().detach().numpy()
    logging.info('Mark embedding features = {}'.format(z.shape))
    np.savetxt(os.path.join(args.out_dir, 'u_emb.npy'), z)
    logging.info('Saved mark embedding features (z).')
    
    if args.encoder_type == 'RNN' or z.shape[0] > 10000:
        logging.info('sent to output directory: (none: I.npy)')
        logging.info('Either model type is RNN or user/marks is large, skipping I.npy')
    else:
        ## attention weights
        dl_list = [dl_train]  # , dl_val, dl_test]
        dl_names = ['Train']  # , 'Val', 'Test']
        A = None; C = None
        for dl_, name in zip(dl_list, dl_names):
            logging.info(name)
            for i, input in enumerate(dl_):
                input = move_input_batch_to_device(input, args.device)
                A_attn, counts = model.attention_weights(input, args.device)
                if type(A) != type(None):
                    A += A_attn
                    C += counts
                else:
                    A = A_attn
                    C = counts
                if i % 50 == 0:
                    logging.info(f'done batch {i}/{len(dl_)}')
                # break
        logging.info('Attention weights extracted. Now attempting to write to file')
        # torch.save(A, os.path.join(args.out_dir, 'attn_weights.pt'))
        # torch.save(C, os.path.join(args.out_dir, 'attn_counts.pt'))
        # logging.info('sent to output directory: attn_weights and attn_counts to get I.npy')
        
        attn_weights = A.numpy()
        attn_counts = C.numpy()
        np.save(os.path.join(args.out_dir, 'attn_weights.npy'), attn_weights)  # A 
        np.save(os.path.join(args.out_dir, 'attn_counts.npy'), attn_counts)  # C

        I = attn_weights/attn_counts
        np.nan_to_num(I, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        np.save(os.path.join(args.out_dir, 'I.npy'), I)  # influence A/C
        logging.info('sent to output directory: I.npy')
    

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='AMDN (Attentive mixture density network) \
    Training and inference of AMDN model, and extraction of learned interactions. In AMDN code, \
    minimum required length of sequences is 2, since in_times, out_times are required in prediction.\
    To include more events add a EOS token, so that marks/time prediction can be handled if only 1 event\
    is in in_time and none in out_time. Or assume inactive users and no influence on peers is same.')
    
    """
    We model sequence of events on the network (u, t) pairs and while predicting the distribution of the next
    event time and type, we learn the influence structure between event types. 
    - it can capture retweet patterns (twitter provides only source-> all tweets links)
    - it can capture latent/hidden influence patterns (accounts who post independently but synchronously)
    """
    
    ## dataset and output directories
    parser.add_argument('--data_dir', type=str, default='/home/krsharma/election2020/dataset/sequences/')
    parser.add_argument('--data_prefix', type=str, default='data', help='pkl files stored as dataprefix_{split}.csv')
    parser.add_argument('--out_dir', type=str, default='/home/krsharma/election2020/dataset/sequences/amdn/')
    parser.add_argument('--log_filename', type=str, default='run.log')
    parser.add_argument('--max_seq_length', type=int, default=128, help='process_seqs breakdown length.')
    
    ## model encoder parameters
    parser.add_argument('--encoder_type', type=str, default='ATTN', help='{RNN, ATTN, (avoid:ATTN_RNN)}')
    parser.add_argument('--history_size', type=int, default=None, help='history/context vec dim: Set as None if ATTN or ATTN_RNN encoder.')
    parser.add_argument('--rnn_type', type=str, default='GRU', help='{RNN, LSTM, GRU}')
    parser.add_argument('--mark_embedding_size', type=int, default=32, help='marks vec dim')
    
    parser.add_argument('--heads', type=int, default=1)
    parser.add_argument('--depth', type=int, default=1)
    parser.add_argument('--wide', dest='wide', default=True, action='store_true', help='Change back')
    
    parser.add_argument('--pos_enc', dest='pos_enc', default=False, action='store_true')  
    # false means mercer's time_enc which includes pos encoding concatenated to it, will be used.
    parser.add_argument('--add', default=0, type=int,
                        help='add or concat (1 to add, 0 to concat) pos, marks, time encodings')
    parser.add_argument('--time_opt', default='delta', help='cumsum_exp/cumsum/delta')
    parser.add_argument('--expand_dim', type=int, default=10, help='frequencies in mercer emb')

    ## model decoder parameters
    parser.add_argument('--decoder_name', type=str, default='LogNormMix')
    parser.add_argument('--n_components', type=int, default=5)
    parser.add_argument('--trainable_affine', dest='trainable_affine', default=True, action='store_true')
    parser.add_argument('--hypernet_hidden_sizes', nargs='+', type=int, default=[], help='mlp_hdims')
    
    ## training arguments
    parser.add_argument('--seed', type=int, default=22)
    parser.add_argument('--regularization', type=float, default=1e-5)
    parser.add_argument('--learning_rate', type=float, default=1e-3)
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--device', type=str, default='cuda')
    parser.add_argument('--max_epochs', type=int, default=50)  # 1000 
    parser.add_argument('--patience', type=int, default=10)
    parser.add_argument('--save_freq', type=int, default=1)
    parser.add_argument('--display_step', type=int, default=1)

    ## pre-set arguments
    parser.add_argument('--use_history', dest='use_history', default=True, action='store_true')
    parser.add_argument('--use_marks', dest='use_marks', default=True, action='store_true')
    parser.add_argument('--use_embedding', dest='use_embedding', default=False, action='store_true')
    parser.add_argument('--embedding_size', default=None, help='seq embedding size.')
    parser.add_argument('--max_degree', default=None, help='flow-based models.')
    parser.add_argument('--n_terms', default=None, help='flow-based models.')
    parser.add_argument('--n_layers', default=None, help='flow-based models.')
    parser.add_argument('--layer_size', default=None, help='flow-based models.')
    
    args = parser.parse_args()
    if not os.path.isdir(args.out_dir): os.makedirs(args.out_dir)
    np.random.seed(args.seed); torch.manual_seed(args.seed);
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='[{%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(filename=os.path.join(args.out_dir, args.log_filename)),
            logging.StreamHandler(sys.stdout)
        ]
    ) # logger = logging.getLogger('')
    logging.info('Logging any runs of this program - appended to same file.')
    logging.info('Arguments = {}'.format(args))
    dl_train, dl_val, dl_test, mean_out_train, std_out_train, num_classes, num_sequences = load_data(args)
    logging.info('loaded the dataset and formed torch dataloaders.')
    model, opt = create_model(num_classes, num_sequences, args, mean_out_train, std_out_train)
    logging.info('model created from config hyperparameters.')
    train(model, opt, dl_train, dl_val, logging, args.use_marks, args.max_epochs, args.patience, 
          args.display_step, args.save_freq, args.out_dir, args.device)
    
    def evaluate(model, dl_list, dl_names, use_marks, device):
        # Calculate the train/val/test loss, plot training curve
        model.eval()
        for dl_, name in zip(dl_list, dl_names):
            loss_tot, time_nll, marks_nll, marks_acc = get_total_loss(
                    dl_, model, args.use_marks, device)
            logging.info(f'{name}: {loss_tot:.4f}')
            logging.info(f'TimeNLL:{time_nll:.4f} MarksNLL:{marks_nll:.4f} Acc:{marks_acc:.4f}')
    dl_list = [dl_train, dl_val, dl_test]
    dl_names = ['Train', 'Val', 'Test']
    evaluate(model, dl_list, dl_names, args.use_marks, args.device)
    model = torch.load(args.out_dir + 'best_full_model.pt')
    
    extract_features(model, logging, args)
    logging.info('Finished program.')