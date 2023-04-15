import torch
import torch.utils.data as Data
from transformers import BertModel
from datasets import load_from_disk
from transformers import BertTokenizer
from transformers import AdamW
from common import *
import os
os.environ['NO_PROXY'] = 'huggingface.co'

def get_train_args():
    parser=argparse.ArgumentParser()
    parser.add_argument('--batch_size',type=int,default=1,help = '每批数据的数量')
    parser.add_argument('--nepoch',type=int,default=3,help = '训练的轮次')
    parser.add_argument('--lr',type=float,default=5e-4,help = '学习率')
    # parser.add_argument('--num_workers',type=int,default=NUM_WORKERS,help='dataloader使用的线程数量')
    parser.add_argument('--num_labels',type=int,default=2,help='分类类数')
    opt=parser.parse_args()
    print(opt)
    return opt

def main(opt):
    global train_acc
    pretrained_model = BertModel.from_pretrained('bert-base-chinese', cache_dir=bert_data_path+'/model/')  # 加载预训练模型
    model = Bert_Model(pretrained_model, opt)  # 构建自己的模型
    if os.path.exists(bert_data_path+'/model/bert_model.pth'):
        model.load_state_dict(torch.load(bert_data_path+'/model/bert_model.pth'))
    # 如果有 gpu, 就用 gpu
    if torch.cuda.is_available():
        model.to(device)
    # train_data = load_from_disk(bert_data_path+'/data/ChnSentiCorp/')['train']  # 加载训练数据
    # test_data = load_from_disk(bert_data_path+'/data/ChnSentiCorp/')['test']  # 加载测试数据

    csv_file_path = bert_data_path+'/data/train'
    train_dataset = csvToDataset(csv_file_path)
    csv_file_path = bert_data_path+'/data/test'
    test_dataset = csvToDataset(csv_file_path)

    optimizer = AdamW(model.parameters(), lr=opt.lr)  # 优化器
    criterion = torch.nn.CrossEntropyLoss()  # 损失函数
    epochs = opt.nepoch  # 训练次数
    # 训练模型
    epoch_bar = tqdm(total=epochs, ncols=TQDM_NCOLS, leave=False)
    for i in range(epochs):
        # print("--------------- >>>> epoch : {} <<<< -----------------".format(i))
        train(model, train_dataset, criterion, optimizer, opt)
        test(model, test_dataset, opt)
        torch.save(model.state_dict(),bert_data_path+'/model/bert_model.pth')
        epoch_bar.update(1)
        epoch_bar.set_description("train acc: %.2e test acc: %.2e" % (train_acc, test_acc))
    epoch_bar.close()

def train(model, dataset, criterion, optimizer, opt):
    global test_acc, last_save_time, train_acc
    loader_train = Data.DataLoader(dataset=dataset,
                                   batch_size=opt.batch_size,
                                   collate_fn=collate_fn,
                                   shuffle=True,  
                                   drop_last=True)  
    model.train()
    total_acc_num = 0
    train_num = 0
    iter_bar = tqdm(total=len(loader_train), ncols=TQDM_NCOLS, leave=False)
    for i, (input_ids, attention_mask, token_type_ids, labels) in enumerate(loader_train):
        output = model(input_ids=input_ids, 
                       attention_mask=attention_mask, 
                       token_type_ids=token_type_ids)  
        loss = criterion(output, labels)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        output = output.argmax(dim=1)  
        accuracy_num = (output == labels).sum().item()
        total_acc_num += accuracy_num
        train_num += loader_train.batch_size
        iter_bar.update(1)
        iter_bar.set_description("loss: %.2e acc: %.2e" % (loss.item(), total_acc_num / train_num))
        if i % (len(loader_train) / 10) == 0 and time.time() - last_save_time > SAVE_INTERVAL:
            torch.save(model.state_dict(),bert_data_path+'/model/bert_model.pth')
            last_save_time = time.time()
            # print("train_schedule: [{}/{}] train_loss: {} train_acc: {}".format(i, len(loader_train),
            #                                                                     loss.item(), total_acc_num / train_num))
    iter_bar.close()
    train_acc = total_acc_num / train_num
    # print("total train_acc: {}".format(total_acc_num / train_num))


def test(model, dataset, opt):
    global test_acc
    correct_num = 0
    test_num = 0
    loader_test = Data.DataLoader(dataset=dataset,
                                  batch_size=opt.batch_size,
                                  collate_fn=collate_fn,
                                  shuffle=True,
                                  drop_last=True)
    model.eval()
    for t, (input_ids, attention_mask, token_type_ids, labels) in enumerate(loader_test):
        with torch.no_grad():
            output = model(input_ids=input_ids,  
                           attention_mask=attention_mask,  
                           token_type_ids=token_type_ids)  
        output = output.argmax(dim=1)
        correct_num += (output == labels).sum().item()
        test_num += loader_test.batch_size
        # if t % 10 == 0:
        #     print("schedule: [{}/{}] acc: {}".format(t, len(loader_test), correct_num / test_num))
    test_acc = correct_num / test_num
    # print("total test_acc: {}".format(correct_num / test_num))


def collate_fn(data):
    sentences = [tuple_x['text'] for tuple_x in data]
    labels = [tuple_x['label'] for tuple_x in data]
    token = BertTokenizer.from_pretrained('bert-base-chinese', cache_dir='./my_vocab')
    data = token.batch_encode_plus(batch_text_or_text_pairs=sentences,
                                   truncation=True,
                                   max_length=max_length,
                                   padding='max_length',
                                   return_tensors='pt',
                                   return_length=True)
    input_ids = data['input_ids'] 
    attention_mask = data['attention_mask'] 
    token_type_ids = data['token_type_ids'] 
    labels = torch.LongTensor(labels)
    if torch.cuda.is_available(): 
        input_ids = input_ids.to(device)
        attention_mask = attention_mask.to(device)
        token_type_ids = token_type_ids.to(device)
        labels = labels.to(device)
    return input_ids, attention_mask, token_type_ids, labels


if __name__ == '__main__':
    global test_acc, last_save_time, train_acc
    max_length = 500
    last_save_time = 0
    test_acc = 0
    train_acc = 0
    opt = get_train_args()
    # device = 'cuda' if torch.cuda.is_available() else 'cpu'  # 全局变量
    print('Use: ', device)
    main(opt)

