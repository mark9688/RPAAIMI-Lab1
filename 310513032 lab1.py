import os
import warnings
import numpy as np
from tqdm import tqdm
import gc
from argparse import ArgumentParser

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from torchvision import transforms
import torchvision.models as models
from torchvision.datasets import ImageFolder

import seaborn as sns
from matplotlib.ticker import MaxNLocator
import matplotlib.pyplot as plt



def measurement(outputs, labels, smooth=1e-10):
    tp, tn, fp, fn = smooth, smooth, smooth, smooth
    labels = labels.cpu().numpy()
    outputs = outputs.detach().cpu().clone().numpy()
    for j in range(labels.shape[0]):
        if (int(outputs[j]) == 1 and int(labels[j]) == 1):
            tp += 1
        if (int(outputs[j]) == 0 and int(labels[j]) == 0):
            tn += 1
        if (int(outputs[j]) == 1 and int(labels[j]) == 0):
            fp += 1
        if (int(outputs[j]) == 0 and int(labels[j]) == 1):
            fn += 1
    return tp, tn, fp, fn

def plot_accuracy(train_acc_list, val_acc_list):
    # TODO plot training and testing accuracy curve
    plt.figure(1)
    plt.title("Training Accuracy")
    plt.xlabel("iter")
    plt.ylabel("train accuracy")
    plt.plot(train_acc_list,markersize="4",marker="o")
    plt.savefig('train.png')

    plt.figure(2)
    plt.title("Testing Accuracy")
    plt.xlabel("iter")
    plt.ylabel("testing accuracy")
    plt.plot(val_acc_list,markersize="4",marker="o")
    plt.savefig('test.png')


def plot_f1_score(f1_score_list):
    # TODO plot testing f1 score curve
    plt.figure(3)
    plt.title("Testing F1 Score")
    plt.xlabel("iter")
    plt.ylabel("f1 score")
    plt.plot(f1_score_list,markersize="4",marker="o")
    plt.savefig('f1score.png')

def plot_confusion_matrix(confusion_matrix):
    # TODO plot confusion matrix
    plt.figure(4)
    plt.title("Confusion matrix")
    heat = sns.heatmap(confusion_matrix, annot=True, fmt="g")
    heat.set_xticklabels({'Predicted Normal','Predicted Pneumonia'})
    heat.set_yticklabels({'Actual Pneumonia','Actual Normal'})
    heatfig = heat.get_figure()
    heatfig.savefig('confusion.png')

def train(device, train_loader, model, criterion, optimizer):
    best_acc = 0.0
    best_model_wts = None
    train_acc_list = []
    val_acc_list = []
    f1_score_list = []
    best_c_matrix = []
    torch.cuda.empty_cache()
    for epoch in range(1, args.num_epochs+1):

        with torch.set_grad_enabled(True):
            avg_loss = 0.0
            train_acc = 0.0
            tp, tn, fp, fn = 0, 0, 0, 0     
            for _, data in enumerate(tqdm(train_loader)):
                inputs, labels = data
                inputs = inputs.to(device)
                labels = labels.to(device)

                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                avg_loss += loss.item()
                outputs = torch.max(outputs, 1).indices
                sub_tp, sub_tn, sub_fp, sub_fn = measurement(outputs, labels)
                tp += sub_tp
                tn += sub_tn
                fp += sub_fp
                fn += sub_fn          

            avg_loss /= len(train_loader.dataset)
            train_acc = (tp+tn) / (tp+tn+fp+fn) * 100
            print(f'Epoch: {epoch}')
            print(f'↳ Loss: {avg_loss}')
            print(f'↳ Training Acc.(%): {train_acc:.2f}%')

        val_acc, f1_score, c_matrix = test(test_loader, model)
        train_acc_list.append(train_acc)
        val_acc_list.append(val_acc)
        f1_score_list.append(f1_score)

        if val_acc > best_acc:
            best_acc = val_acc
            best_c_matrix = c_matrix
            torch.save(model.state_dict(), 'best_model_weights.pt')

    return train_acc_list, val_acc_list, f1_score_list, best_c_matrix

def test(test_loader, model):
    val_acc = 0.0
    tp, tn, fp, fn = 0, 0, 0, 0
    with torch.set_grad_enabled(False):
        model.eval()
        for images, labels in test_loader:
            
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            outputs = torch.max(outputs, 1).indices

            sub_tp, sub_tn, sub_fp, sub_fn = measurement(outputs, labels)
            tp += sub_tp
            tn += sub_tn
            fp += sub_fp
            fn += sub_fn

        c_matrix = [[int(tp), int(fn)],
                    [int(fp), int(tn)]]
        
        val_acc = (tp+tn) / (tp+tn+fp+fn) * 100
        recall = tp / (tp+fn)
        precision = tp / (tp+fp)
        f1_score = (2*tp) / (2*tp+fp+fn)
        print (f'↳ Recall: {recall:.4f}, Precision: {precision:.4f}, F1-score: {f1_score:.4f}')
        print (f'↳ Test Acc.(%): {val_acc:.2f}%')

    return val_acc, f1_score, c_matrix

if __name__ == '__main__':
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    warnings.filterwarnings('ignore', category=UserWarning)
  

    parser = ArgumentParser()

    # for model
    parser.add_argument('--num_classes', type=int, required=False, default=2)

    # for training
    parser.add_argument('--num_epochs', type=int, required=False, default=30)
    parser.add_argument('--batch_size', type=int, required=False, default=128)
    parser.add_argument('--lr', type=float, default=1e-5)
    parser.add_argument('--wd', type=float, default=0.9)

    # for dataloaderX
    parser.add_argument('--dataset', type=str, required=False, default='chest_xray')

    # for data augmentation
    parser.add_argument('--degree', type=int, default=90)
    parser.add_argument('--resize', type=int, default=224)

    args = parser.parse_args()

    # set gpu
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'## Now using {device} as calculating device ##')

    # set dataloader
    train_dataset = ImageFolder(root=os.path.join(args.dataset, 'train'),
                                transform = transforms.Compose([transforms.Resize((args.resize, args.resize)),
                                                                transforms.RandomRotation(args.degree, resample=False),
                                                                transforms.ToTensor()]))
    test_dataset = ImageFolder(root=os.path.join(args.dataset, 'test'),
                               transform = transforms.Compose([transforms.Resize((args.resize, args.resize)),
                                                               transforms.ToTensor()]))

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)

    # define model
    model = models.resnet18(pretrained=True)
    num_neurons = model.fc.in_features
    model.fc = nn.Linear(num_neurons, args.num_classes)
    model = model.to(device)

    # define loss function, optimizer
    criterion = nn.CrossEntropyLoss(weight=torch.FloatTensor([3.8896346, 1.346]))
    criterion = criterion.to(device)
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.wd)

    # training
    train_acc_list, val_acc_list, f1_score_list, best_c_matrix = train(device, train_loader, model, criterion, optimizer)

    # plot
    plot_accuracy(train_acc_list, val_acc_list)
    plot_f1_score(f1_score_list)
    plot_confusion_matrix(best_c_matrix)