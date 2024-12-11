# -*- coding: utf-8 -*-
"""gan_fraud_detection_better.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/16jlIlSghWR3XxGA7c74iAHsSQiWGb_9k

credit: https://www.kaggle.com/code/ttunjic/gans-for-tabular-data/notebook

https://www.kaggle.com/code/techytushar/tabular-data-generation-using-gans
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn import preprocessing
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score,\
                            accuracy_score, balanced_accuracy_score,classification_report,\
                            ConfusionMatrixDisplay, confusion_matrix
from sklearn.model_selection import KFold, GridSearchCV
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

import lightgbm as lgb
import tensorflow as tf
import keras
from keras.layers import Input, Dense, Reshape, Flatten, Dropout, multiply, Concatenate
from keras.layers import BatchNormalization, Activation, Embedding, ZeroPadding2D, LeakyReLU
from keras.models import Sequential, Model
from keras.optimizers import Adam
from keras.initializers import RandomNormal
import keras.backend as K
from sklearn.utils import shuffle
from imblearn.over_sampling import SMOTE


np.random.seed(34)



class cGAN():
    def __init__(self):
        self.latent_dim = 32
        self.out_shape = 29
        self.num_classes = 2
        self.clip_value = 0.01
        #optimizer = RMSprop(lr=0.00005)

        # build discriminator
        self.discriminator = self.build_discriminator()
        self.discriminator.compile(loss=['binary_crossentropy'],
                                   optimizer=Adam(0.0002, 0.5),
                                   metrics=['accuracy'])

        # build generator
        self.generator = self.build_generator()

        # generating new data samples
        noise = Input(shape=(self.latent_dim,))
        label = Input(shape=(1,))
        gen_samples = self.generator([noise, label])
        print(gen_samples)
        self.discriminator.trainable = False

        # passing gen samples through disc. 
        valid = self.discriminator([gen_samples, label])

        # combining both models
        self.combined = Model([noise, label], valid)
        self.combined.compile(loss=['binary_crossentropy'],
                              optimizer=Adam(0.0002, 0.5),
                             metrics=['accuracy'])
        self.combined.summary()

    def wasserstein_loss(self, y_true, y_pred):
        return K.mean(y_true * y_pred)

    def build_generator(self):
        init = RandomNormal(mean=0.0, stddev=0.02)
        model = Sequential()

        model.add(Dense(128, input_dim=self.latent_dim))
        #model.add(Dropout(0.2))
        model.add(LeakyReLU(alpha=0.2))
        model.add(BatchNormalization(momentum=0.8))

        model.add(Dense(256))
        #model.add(Dropout(0.2))
        model.add(LeakyReLU(alpha=0.2))
        model.add(BatchNormalization(momentum=0.8))

        model.add(Dense(512))
        #model.add(Dropout(0.2))
        model.add(LeakyReLU(alpha=0.2))
        model.add(BatchNormalization(momentum=0.8))

        model.add(Dense(self.out_shape, activation='tanh'))
        model.summary()

        noise = Input(shape=(self.latent_dim,))
        label = Input(shape=(1,), dtype='int32')
        label_embedding = Flatten()(Embedding(self.num_classes, self.latent_dim)(label))
        
        model_input = multiply([noise, label_embedding])
        gen_sample = model(model_input)

        return Model([noise, label], gen_sample, name="Generator")

    
    def build_discriminator(self):
        init = RandomNormal(mean=0.0, stddev=0.02)
        model = Sequential()

        model.add(Dense(512, input_dim=self.out_shape, kernel_initializer=init))
        model.add(LeakyReLU(alpha=0.2))
        
        model.add(Dense(256, kernel_initializer=init))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.4))
        
        model.add(Dense(128, kernel_initializer=init))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.4))
        
        model.add(Dense(1, activation='sigmoid'))
        model.summary()
        
        gen_sample = Input(shape=(self.out_shape,))
        label = Input(shape=(1,), dtype='int32')
        label_embedding = Flatten()(Embedding(self.num_classes, self.out_shape)(label))

        model_input = multiply([gen_sample, label_embedding])
        validity = model(model_input)

        return Model(inputs=[gen_sample, label], outputs=validity, name="Discriminator")


    def train(self, X_train, y_train, pos_index, neg_index, count, epochs, batch_size=32, sample_interval=50):

        # Adversarial ground truths
        valid = np.ones((batch_size, 1))
        fake = np.zeros((batch_size, 1))
        G_losses=[]
        D_losses=[]
        
        for epoch in range(epochs):
            
            #  Train Discriminator with 8 sample from postivite class and rest with negative class
            idx1 = np.random.choice(pos_index, 8)
            idx0 = np.random.choice(neg_index, batch_size-8)
            idx = np.concatenate((idx1, idx0))
            samples, labels = X_train[idx], y_train[idx]
            samples, labels = shuffle(samples, labels)
            # Sample noise as generator input
            noise = np.random.normal(0, 1, (batch_size, self.latent_dim))

            # Generate a half batch of new images
            gen_samples = self.generator.predict([noise, labels])

            # label smoothing
            if epoch < epochs//1.5:
                valid_smooth = (valid+0.1)-(np.random.random(valid.shape)*0.1)
                fake_smooth = (fake-0.1)+(np.random.random(fake.shape)*0.1)
            else:
                valid_smooth = valid 
                fake_smooth = fake
                
            # Train the discriminator
            self.discriminator.trainable = True
            d_loss_real = self.discriminator.train_on_batch([samples, labels], valid_smooth)
            d_loss_fake = self.discriminator.train_on_batch([gen_samples, labels], fake_smooth)
            d_loss = 0.5 * np.add(d_loss_real, d_loss_fake)

            # Train Generator
            # Condition on labels
            self.discriminator.trainable = False
            sampled_labels = np.random.randint(0, 2, batch_size).reshape(-1, 1)
            # Train the generator
            g_loss = self.combined.train_on_batch([noise, sampled_labels], valid)

            # Plot the progress
            if (epoch+1)%sample_interval==0:
                print (f"[Generator] {count+1}: {epoch} [D loss: {d_loss[0]}, acc.: {100*d_loss[1]}] [G loss: {g_loss}]")
            G_losses.append(g_loss[0])
            D_losses.append(d_loss[0])
            if epoch+1==epochs:
                plt.figure(figsize=(10,5))
                plt.title("Generator and Discriminator Loss")
                plt.plot(G_losses,label="G")
                plt.plot(D_losses,label="D")
                plt.xlabel("iterations")
                plt.ylabel("Loss")
                plt.legend()
                plt.show()
                plt.savefig(f'losses-{count+1}.png')


np.random.seed(34)
df = pd.read_csv('creditcard.csv', encoding='utf-8', sep=',')
df = df.drop(columns='Time')
df = df.drop_duplicates()

df.Class.value_counts()
df['Amount'] = df['Amount'].apply(lambda x: np.log10(x+1))
    

scaler = StandardScaler()

X = scaler.fit_transform(df.drop(columns='Class'))
y = df['Class'].values

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, stratify=y)

print(type(y_train))


train_combined = pd.DataFrame(X_train)

column_series = y_train.tolist()

train_combined['Class'] = column_series

notfraud=train_combined[train_combined.Class==0]
fraud=train_combined[train_combined.Class==1]

dfs = np.array_split(notfraud,60)

for count, df_sub in enumerate(dfs):
    dfs[count] = pd.concat([df_sub, fraud])

gans = []

for count, df_sub in enumerate(dfs):
    X_train = df_sub.drop(columns='Class').to_numpy()
    y_train = df_sub['Class'].values

    lgb_1 = lgb.LGBMClassifier()
    lgb_1.fit(X_train, y_train)

    y_pred = lgb_1.predict(X_test)

    # evaluation
    print(classification_report(y_test, y_pred))
    ConfusionMatrixDisplay.from_estimator(lgb_1, X_test, y_test)
    plt.show()
    plt.savefig(f'fig1-{count+1}.png')
    
    smote=SMOTE(sampling_strategy='minority') 
    X_train,y_train=smote.fit_resample(X_train,y_train)
    lgb_1 = lgb.LGBMClassifier()
    lgb_1.fit(X_train, y_train)

    y_pred = lgb_1.predict(X_test)

    # evaluation
    print(classification_report(y_test, y_pred))
    ConfusionMatrixDisplay.from_estimator(lgb_1, X_test, y_test)
    plt.show()
    plt.savefig(f'fig1-{count+1}-smote.png')

    cgan = cGAN()
    y_train = y_train.reshape(-1,1)
    pos_index = np.where(y_train==1)[0]
    neg_index = np.where(y_train==0)[0]
    cgan.train(X_train, y_train, pos_index, neg_index, count, epochs=2000, sample_interval=50)


    cgan.generator.save(f"generator-{count+1}.keras")
    gans.append(cgan)

    """noise = np.random.normal(0, 1, (52286, 32))
    sampled_labels = np.zeros(52286).reshape(-1, 1)


    gen_samples = cgan.generator.predict([noise, sampled_labels])

    gen_df = pd.DataFrame(data = gen_samples,
                          columns = df.drop(columns="Class").columns)

    noise_2 = np.random.normal(0, 1, (426, 32))
    sampled_labels_2 = np.ones(426).reshape(-1, 1)


    gen_samples_2 = cgan.generator.predict([noise_2, sampled_labels_2])

    gen_df_2 = pd.DataFrame(data = gen_samples_2,
                          columns = df.drop(columns="Class").columns)

    gen_df_2['Class'] = 1
    gen_df['Class']=0

    df_gan = pd.concat([gen_df_2, gen_df], ignore_index=True, sort=False)
    df_gan = df_gan.sample(frac=1).reset_index(drop=True)

    X_train_2 = df_gan.drop(columns="Class")
    y_train_2 = df_gan['Class'].values

    lgb_1 = lgb.LGBMClassifier()
    lgb_1.fit(X_train_2, y_train_2)


    y_pred = lgb_1.predict(X_test)

    print(classification_report(y_test, y_pred))
    ConfusionMatrixDisplay.from_estimator(lgb_1, X_test, y_test)
    plt.show()
    plt.savefig('fig2.png')"""

