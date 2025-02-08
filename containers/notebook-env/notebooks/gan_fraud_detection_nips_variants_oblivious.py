# -*- coding: utf-8 -*-
"""gan_fraud_detection_nips_variants.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1tRAK7dZdQYtmDeaWo-mpfJWXfhpUajjh
"""


from statistics import mean, stdev
import sys
import kagglehub
from pyod.models.ecod import ECOD
from pyod.utils.data import generate_data
from pyod.utils.data import evaluate_print
from pyod.utils.example import visualize
from pyod.models.iforest import IForest
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn import preprocessing
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import precision_score, recall_score, f1_score,\
                            accuracy_score, balanced_accuracy_score,classification_report,\
                            ConfusionMatrixDisplay, confusion_matrix, \
                            precision_recall_fscore_support, auc, roc_curve
from sklearn.model_selection import KFold, GridSearchCV
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier

import lightgbm as lgb
import xgboost as xgb
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
import keras
from keras.layers import Input, Dense, Reshape, Flatten, Dropout, multiply, Concatenate
from keras.layers import BatchNormalization, Activation, Embedding, ZeroPadding2D, LeakyReLU
from keras.models import Sequential, Model
from keras.optimizers import Adam
from keras.initializers import RandomNormal
import keras.backend as K
from sklearn.utils import shuffle
from imblearn.over_sampling import SMOTE

# Download latest version
path = kagglehub.dataset_download("sgpjesus/bank-account-fraud-dataset-neurips-2022")

print("Path to dataset files:", path)

path2 = kagglehub.dataset_download("ealaxi/paysim1")

print("Path to dataset files:", path2)

path3 = kagglehub.dataset_download("ealtman2019/credit-card-transactions")

print("Path to dataset files:", path3)




np.random.seed(34)

#objective = "reg:squarederror"
#objective = "reg:squaredlogerror"
objective = "binary:logistic"
#objective = "reg:logistic"

def print_cls_report(y_test, y_pred, title):
    # Calculate the classification report
    default_report = classification_report(y_test, y_pred, target_names=['No Fraud', 'Fraud'])

    # Calculate precision, recall, f1 score and support for each class
    precision, recall, f1_score, support = precision_recall_fscore_support(y_test, y_pred)

    # Print the title and the default classification report
    print(title)
    print('*****' * 10)
    print(default_report)

    # Return the recall scores for each class
    return recall

def plot_con_matrix(ax, y_test, y_pred, title):
    # Define the classes of the classification problem
    classes = ['No Fraud', 'Fraud']

    # Compute the confusion matrix
    con_matrix = confusion_matrix(y_test, y_pred)

    # Compute the values for true negatives, false positives, false negatives, and true positives
    tn, fp, fn, tp = con_matrix.ravel()

    # Compute the false positive rate
    fpr = fp / (fp + tn)

    # Plot the confusion matrix using a heatmap
    ax.imshow(con_matrix, interpolation='nearest', cmap=plt.cm.Blues)

    # Define the tick marks and the labels for the plot
    tick_marks = np.arange(len(classes))
    ax.set_xticks(tick_marks)
    ax.set_xticklabels(classes)
    ax.set_yticks(tick_marks)
    ax.set_yticklabels(classes)

    # Add the count of each cell of the confusion matrix to the plot
    fmt = 'd'
    threshold = con_matrix.max() / 2.
    for i, j in np.ndindex(con_matrix.shape):
        ax.text(j, i, format(con_matrix[i, j], fmt),
                 horizontalalignment="center",
                 color="white" if con_matrix[i, j] > threshold else "black")

    # Add labels to the plot
    ax.set_xlabel('Predicted label')
    ax.set_ylabel('True label')
    ax.set_title(f'{title} with {fpr*100:.2f}% FPR')

def print_cv_results(model):
    # Get the parameter and score arrays from the cv_results_ dictionary
    means = model.cv_results_['mean_test_score']
    params = model.cv_results_['params']

    # Combine the arrays using zip()
    combined_results = zip(means, params)

    # Sort the combined array by mean_test_score in descending order
    sorted_results = sorted(combined_results, key=lambda x: x[0], reverse=True)

    # Print the mean test score and the hyperparameters as a formatted string
    for mean, param in sorted_results:
        print("mean_test_score: %f, params: %r" % (mean, param))

def plot_roc_curves(fpr_list, tpr_list, label_list):
    plt.figure(figsize=(8, 8))
    for i in range(len(fpr_list)):
        # Compute the ROC AUC score
        roc_auc_score = auc(fpr_list[i], tpr_list[i])
        # Plot the ROC curve
        plt.plot(fpr_list[i], tpr_list[i], label=f'{label_list[i]} (AUC={roc_auc_score:.2f})')

    # Plot the random classifier curve
    plt.plot([0, 1], [0, 1], 'k--', label='Random')

    # Set the plot labels and title
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver Operating Characteristic (ROC) Curve')
    plt.legend()

def test_classifier(classifier, X_test, y_test):
    """
    Evaluates a binary classifier by generating ROC curves, classification reports, and confusion matrices.

    Parameters:
    -----------
    classifier : classifier object
        Binary classifier object to be evaluated.
    X_test : numpy.ndarray or pandas.DataFrame
        Test feature data.
    y_test : numpy.ndarray or pandas.Series
        Test target labels.

    Returns:
    --------
    tuple : A tuple containing four values - false positive rate (fpr), true positive rate (tpr),
            default recall, and target recall.
    """

    # Predict class probabilities and labels using the trained classifier
    y_pred = classifier.predict(X_test)
    y_prob = classifier.predict_proba(X_test)[:, 1]

    # Calculate the false positive rate and true positive rate for different threshold values
    fpr, tpr, thresholds = roc_curve(y_test, y_prob)

    # Choose a false positive rate threshold based on the ROC curve
    target_fpr = 0.05
    threshold_idx = np.argmin(np.abs(fpr - target_fpr))
    threshold = thresholds[threshold_idx]

    # Make predictions on the testing set using the threshold
    y_pred_threshold = (y_prob >= threshold).astype(int)

    # Print the classification report for both default and target threshold
    default_recall = print_cls_report(y_test, y_pred, title="Default Threshold")
    target_recall = print_cls_report(y_test, y_pred_threshold, title=f'Target Threshold @ {threshold:.2f}')

    # Plot confusion matrix
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    default_matrix = plot_con_matrix(ax1, y_test, y_pred, title='Default Threshold @ 0.50')
    target_matrix = plot_con_matrix(ax2, y_test, y_pred_threshold, title=f'Target Threshold @ {threshold:.2f}')

    # Adjust subplots for better visibility
    plt.tight_layout()

    # Display the plots

    return fpr, tpr, default_recall, target_recall

class cGAN():
    def __init__(self, out_shape):
        self.latent_dim = 32
        self.out_shape = out_shape
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


    def train(self, X_train, y_train, pos_index, neg_index, epochs, batch_size=32, sample_interval=50):

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
                print (f"{epoch} [D loss: {d_loss[0]}, acc.: {100*d_loss[1]}] [G loss: {g_loss}]")
            G_losses.append(g_loss[0])
            D_losses.append(d_loss[0])


baf = ["variant1", "variant2", "variant3", "variant4", "variant5", "baf_base"]

#data_name = "variant1"
#data_name = "variant2"
#data_name = "variant3"
#data_name = "variant4"
#data_name = "variant5"
#data_name = "baf_base"
#data_name = "eucch"
#data_name = "paysim"
#data_name = "cct"

conceptDrift = True

xgb_inc_np = XGBClassifier(random_state=42, scale_pos_weight=0.5, objective=objective)
xgb_inc_smote = XGBClassifier(random_state=42, scale_pos_weight=0.5, objective=objective)
xgb_inc_gan = XGBClassifier(random_state=42, scale_pos_weight=0.5, objective=objective)
xgb_inc_esmote = []
for i in range(60):
    xgb_inc_esmote.append(XGBClassifier(random_state=42, scale_pos_weight=0.5, objective=objective))

#concept_drift_types = ["oblivious", "sliding_window"]
first_gan = False
#for data_name in ["variant1", "variant2", "variant3", "variant4", "variant5", "baf_base", "eucch", "paysim", "cct"]:
for concept_drift_type in ["incremental", "oblivious", "sliding_window"]:
    if concept_drift_type == "incremental":
        first_gan = True
    else:
        first_gan = False
    print(concept_drift_type)
    data_names = ["cct", "baf_base", "variant4", "variant5"]
    no_preprocess_mean = []
    no_preprocess_stdev = []
    smote_mean = []
    smote_stdev = []
    gan_mean = []
    gan_stdev = []
    esmote_mean = []
    esmote_stdev = []
    for data_name in data_names:
        print(data_name)
        match data_name:
          case "variant1":
            df = pd.read_csv(f'{path}/Variant I.csv', encoding='utf-8', sep=',')
          case "variant2":
            df = pd.read_csv(f'{path}/Variant II.csv', encoding='utf-8', sep=',')
          case "variant3":
            df = pd.read_csv(f'{path}/Variant III.csv', encoding='utf-8', sep=',')
          case "variant4":
            df = pd.read_csv(f'{path}/Variant IV.csv', encoding='utf-8', sep=',')
          case "variant5":
            df = pd.read_csv(f'{path}/Variant V.csv', encoding='utf-8', sep=',')
          case "baf_base":
            df = pd.read_csv(f'{path}/Base.csv', encoding='utf-8', sep=',')
          case "eucch":
            df = pd.read_csv('creditcard.csv', encoding='utf-8', sep=',')
          case "paysim":
            df = pd.read_csv(f'{path2}/PS_20174392719_1491204439457_log.csv', encoding='utf-8', sep=',')
          case "cct":
            df = pd.read_csv(f'{path3}/credit_card_transactions-ibm_v2.csv', encoding='utf-8', sep=',', nrows=2438690)
          case default:
            print("Invalid data name")

        if data_name in baf:
          y = df['fraud_bool']
          df = df.drop(columns='fraud_bool')
          df['fraud_bool']=y
        elif data_name == "eucch":
          df = df.drop(columns='Time')
        elif data_name == "paysim":
          df = df.drop(["step", "type", "nameOrig", "nameDest", "isFlaggedFraud"], axis = 1)
        elif data_name == "cct":
          df = df.drop(["User", "Card", "Errors?"], axis = 1)
          df = df.dropna()

        df = df.drop_duplicates()
        column_names = list(df.columns)
        df.head()

        if data_name in baf or data_name == "cct":
          cat_columns = df.select_dtypes(['object']).columns
          df[cat_columns] = df[cat_columns].astype('category')
          cat_columns = df.select_dtypes(['category']).columns
          cat_columns = df.select_dtypes(['category']).columns
          df[cat_columns] = df[cat_columns].apply(lambda x: x.cat.codes)
          df.head()
        if data_name == "eucch":
          df['Amount'] = df['Amount'].apply(lambda x: np.log10(x+1))
          df.head()

        if data_name in baf:
          df.fraud_bool.value_counts()
          
        if data_name == "eucch":
          df.Class.value_counts()
        if data_name == "paysim":
          df.isFraud.value_counts()
        if data_name == "cct":
          print(df["Is Fraud?"].value_counts())
      
    
    
        scaler = StandardScaler()
        if data_name in baf:
            months = [0,1,2,3,4,5,6,7]
        elif data_name == "cct":
            months = [1,2,3,4,5,6,7,8,9,10,11,12]
        if data_name in baf and conceptDrift:
            test_cds = []
            train_cds = []
            if concept_drift_type == "oblivious":
                for i in range(4,8):
                    test_cds.append(df[df["month"]==months[i]])
                    train_cds.append(df.loc[df["month"].isin(months[0:4])])
            if concept_drift_type == "sliding_window":
                for i in range(4,8):
                    test_cds.append(df[df["month"]==months[i]])
                    train_cds.append(df.loc[df["month"].isin(months[i-4:i])])
            if concept_drift_type == "incremental":
                test_cds.append(df[df["month"]==months[4]])
                train_cds.append(df.loc[df["month"].isin(months[0:4])])
                for i in range(5,8):
                    test_cds.append(df[df["month"]==months[i]])
                    train_cds.append(df[df["month"]==months[i-1]])                    
        elif data_name in baf:
          X = scaler.fit_transform(df.drop(columns='fraud_bool'))
          y = df['fraud_bool'].values
        elif data_name == "eucch":
          X = scaler.fit_transform(df.drop(columns='Class'))
          y = df['Class'].values
        elif data_name == "paysim":
          X = scaler.fit_transform(df.drop(columns='isFraud'))
          y = df['isFraud'].values
        if data_name == "cct" and conceptDrift:
            test_cds = []
            train_cds = []
            if concept_drift_type == "oblivious":
                for i in range(6,12):
                    test_cds.append(df[df["Month"]==months[i]])
                    train_cds.append(df.loc[df["Month"].isin(months[0:6])])
            if concept_drift_type == "sliding_window":
                for i in range(6,12):
                    test_cds.append(df[df["Month"]==months[i]])
                    train_cds.append(df.loc[df["Month"].isin(months[i-6:i])])
            if concept_drift_type == "incremental":
                test_cds.append(df[df["Month"]==months[6]])
                train_cds.append(df.loc[df["Month"].isin(months[0:6])])
                for i in range(7,12):
                    test_cds.append(df[df["Month"]==months[i]])
                    train_cds.append(df[df["Month"]==months[i-1]])            
        elif data_name == "cct":
          X = scaler.fit_transform(df.drop(columns='Is Fraud?'))
          y = df['Is Fraud?'].values
        if not conceptDrift:
          X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, stratify=y, random_state=42)

        
        
        f1_no_preprocess=[]
        f1_smote=[]
        f1_gan=[]
        f1_esmote=[]
        
        for test_cd, train_cd in zip(test_cds, train_cds):
            if data_name == "cct":
                X_train = scaler.fit_transform(train_cd.drop(columns='Is Fraud?'))
                y_train = train_cd['Is Fraud?'].values
                X_test = scaler.fit_transform(test_cd.drop(columns='Is Fraud?'))
                y_test = test_cd['Is Fraud?'].values
            elif data_name in baf:
                X_train = scaler.fit_transform(train_cd.drop(columns='fraud_bool'))
                y_train = train_cd['fraud_bool'].values
                X_test = scaler.fit_transform(test_cd.drop(columns='fraud_bool'))
                y_test = test_cd['fraud_bool'].values                
            

            """XGBoost

            No data processing
            """
            if concept_drift_type == "incremental":
                xgb_1 = xgb_inc_np
            else:
                xgb_1 = XGBClassifier(random_state=42, scale_pos_weight=0.5, objective=objective)
            xgb_1.fit(X_train, y_train)

            y_pred = xgb_1.predict(X_test)

            # evaluation
            print(classification_report(y_test, y_pred))
            xgb_results = test_classifier(xgb_1, X_test, y_test)
            if concept_drift_type == "incremental":
                xgb_inc_np = xgb_1            

            f1_xgb =[]
            f1_xgb.append(xgb_results[3][1])
            f1_no_preprocess.append(xgb_results[3][1])

            """SMOTE"""

            smote=SMOTE(sampling_strategy='minority')
            X_train_2,y_train_2=smote.fit_resample(X_train,y_train)
            if concept_drift_type == "incremental":
                xgb_1 = xgb_inc_smote
            else:
                xgb_1 = XGBClassifier(random_state=42, scale_pos_weight=0.5, objective=objective)
            xgb_1.fit(X_train_2, y_train_2)

            y_pred = xgb_1.predict(X_test)

            # evaluation
            print(classification_report(y_test, y_pred))
            xgb_results = test_classifier(xgb_1, X_test, y_test)
            
            if concept_drift_type == "incremental":
                xgb_inc_smote = xgb_1
            
            f1_xgb.append(xgb_results[3][1])
            f1_smote.append(xgb_results[3][1])

            """GAN"""
            if concept_drift_type != "incremental" or (concept_drift_type == "incremental" and first_gan):
                cgan = cGAN(X_train.shape[1])
                first_gan = False

            y_train = y_train.reshape(-1,1)
            pos_index = np.where(y_train==1)[0]
            neg_index = np.where(y_train==0)[0]
            cgan.train(X_train, y_train, pos_index, neg_index, epochs=200, sample_interval=50)


            cgan.generator.save("generator.keras")
            cgan.discriminator.save("discriminator.keras")

            train_combined = pd.DataFrame(X_train)
            column_series = y_train
            if data_name in baf:
              train_combined['fraud_bool'] = column_series
              diff = train_combined['fraud_bool'].value_counts()[0]-train_combined['fraud_bool'].value_counts()[1]
            elif data_name == "eucch":
              train_combined['Class'] = column_series
              diff = train_combined['Class'].value_counts()[0]-train_combined['Class'].value_counts()[1]
            elif data_name == "paysim":
              train_combined['isFraud'] = column_series
              diff = train_combined['isFraud'].value_counts()[0]-train_combined['isFraud'].value_counts()[1]
            elif data_name == "cct":
              train_combined['Is Fraud?'] = column_series
              diff = train_combined['Is Fraud?'].value_counts()[0]-train_combined['Is Fraud?'].value_counts()[1]
            train_combined = train_combined.set_axis(column_names, axis=1)

            if data_name in baf:
              notfraud=train_combined[train_combined["fraud_bool"]==0]
              fraud=train_combined[train_combined["fraud_bool"]==1]
            elif data_name == "eucch":
              notfraud=train_combined[train_combined["Class"]==0]
              fraud=train_combined[train_combined["Class"]==1]
            elif data_name == "paysim":
              notfraud=train_combined[train_combined["isFraud"]==0]
              fraud=train_combined[train_combined["isFraud"]==1]
            elif data_name == "cct":
              notfraud=train_combined[train_combined["Is Fraud?"]==0]
              fraud=train_combined[train_combined["Is Fraud?"]==1]

            dfs = np.array_split(notfraud,60)
            for count, df_sub in enumerate(dfs):
                dfs[count] = pd.concat([df_sub, fraud])
            
            
            
            generator = keras.models.load_model(f'generator.keras')
            discriminator = keras.models.load_model(f'discriminator.keras')
            noise = np.random.normal(0, 1, (diff, 32))
            sampled_labels = np.ones(diff).reshape(-1, 1)
            gen_samples = generator.predict([noise, sampled_labels])
            gen_probs = discriminator.predict([gen_samples, sampled_labels])
            avg_prob = gen_probs.mean()
            delete_rows = []
            for count, gen_prob in enumerate(gen_probs):
                if gen_prob < avg_prob:
                    delete_rows.append(count)
            gen_samples = np.delete(gen_samples, delete_rows, axis=0)
            if data_name in baf:
              gen_df = pd.DataFrame(data = gen_samples,
                              columns = df.drop(columns="fraud_bool").columns)
              gen_df['fraud_bool']=1
            elif data_name == "eucch":
              gen_df = pd.DataFrame(data = gen_samples,
                              columns = df.drop(columns="Class").columns)
              gen_df['Class']=1
            elif data_name == "paysim":
              gen_df = pd.DataFrame(data = gen_samples,
                              columns = df.drop(columns="isFraud").columns)
              gen_df['isFraud']=1
            elif data_name == "cct":
              gen_df = pd.DataFrame(data = gen_samples,
                              columns = df.drop(columns="Is Fraud?").columns)
              gen_df['Is Fraud?']=1
            df_combined = pd.concat([train_combined, gen_df])
            print(df_combined.shape)
            if data_name in baf:
              X_train_3 = df_combined.drop(columns='fraud_bool').to_numpy()
              y_train_3 = df_combined['fraud_bool'].values
            elif data_name == "eucch":
              X_train_3 = df_combined.drop(columns='Class').to_numpy()
              y_train_3 = df_combined['Class'].values
            elif data_name == "paysim":
              X_train_3 = df_combined.drop(columns='isFraud').to_numpy()
              y_train_3 = df_combined['isFraud'].values
            elif data_name == "cct":
              X_train_3 = df_combined.drop(columns='Is Fraud?').to_numpy()
              y_train_3 = df_combined['Is Fraud?'].values

            if concept_drift_type == "incremental":
                xgb_1 = xgb_inc_gan
            else:
                xgb_1 = XGBClassifier(random_state=42, scale_pos_weight=0.5, objective=objective)
            xgb_1.fit(X_train_3, y_train_3)

            y_pred = xgb_1.predict(X_test)

            # evaluation
            print(classification_report(y_test, y_pred))
            xgb_results = test_classifier(xgb_1, X_test, y_test)
            if concept_drift_type == "incremental":
                xgb_inc_gan = xgb_1

            f1_xgb.append(xgb_results[3][1])
            f1_gan.append(xgb_results[3][1])

            """ESMOTE"""

            rfs = []
            scaler = StandardScaler()
            for count, df_sub in enumerate(dfs):
                smote=SMOTE(sampling_strategy='minority')
                if data_name in baf:
                  X_train_4 = scaler.fit_transform(df_sub.drop(columns='fraud_bool'))
                  y_train_4 = df_sub['fraud_bool'].values
                elif data_name == "eucch":
                  X_train_4 = scaler.fit_transform(df_sub.drop(columns='Class'))
                  y_train_4 = df_sub['Class'].values
                elif data_name == "paysim":
                  X_train_4 = scaler.fit_transform(df_sub.drop(columns='isFraud'))
                  y_train_4 = df_sub['isFraud'].values
                elif data_name == "cct":
                  X_train_4 = scaler.fit_transform(df_sub.drop(columns='Is Fraud?'))
                  y_train_4 = df_sub['Is Fraud?'].values
                X_train_4,y_train_4=smote.fit_resample(X_train_4,y_train_4)
                if concept_drift_type == "incremental":
                    rf_1 = xgb_inc_esmote[count]
                else:
                    rf_1 = XGBClassifier(random_state=42, scale_pos_weight=0.5, objective=objective)
                rf_1.fit(X_train_4, y_train_4)
                rfs.append(rf_1)
                if concept_drift_type == "incremental":
                    xgb_inc_esmote[count] = rf_1

            preds=[]
            probs = []
            weights = []
            rf_count=0
            for count, rf_1 in enumerate(rfs):
                y_pred = rf_1.predict(X_test)
                preds.append(y_pred)
                y_prob = rf_1.predict_proba(X_test)[:, 1]
                probs.append(y_prob)

                # Calculate the false positive rate and true positive rate for different threshold values
                fpr, tpr, thresholds = roc_curve(y_test, y_prob)

                # Choose a false positive rate threshold based on the ROC curve
                target_fpr = 0.05
                threshold_idx = np.argmin(np.abs(fpr - target_fpr))
                threshold = thresholds[threshold_idx]

                # Make predictions on the testing set using the threshold
                y_pred_threshold = (y_prob >= threshold).astype(int)
                _, recall, _, _ = precision_recall_fscore_support(y_test, y_pred)



                weights.append(recall[1])
                rf_count+=1

            test = []
            for j in range(len(probs)):
                test.append([k for k in probs[j]])
            true_probs = np.array(test)
            norm_weights = [float(i)/sum(weights) for i in weights]

            results = []
            count_fraud=0
            count_notfraud=0
            for i in range(len(y_test)):
                res = 0
                for j in range(rf_count):
                    res+=norm_weights[j]*true_probs[j][i]
                if res>=0.5:
                    results.append(1)
                    count_fraud+=1
                else:
                    results.append(0)
                    count_notfraud+=1

            cm = confusion_matrix(y_test, results)
            disp = ConfusionMatrixDisplay(confusion_matrix=cm)
            disp.plot()


            _, recall, _, _ = precision_recall_fscore_support(y_test, results)
            f1_xgb.append(recall[1])
            f1_esmote.append(recall[1])
        
        no_preprocess_mean.append(round(mean(f1_no_preprocess),2))
        no_preprocess_stdev.append(round(stdev(f1_no_preprocess),2))
        smote_mean.append(round(mean(f1_smote),2))
        smote_stdev.append(round(stdev(f1_smote),2))
        gan_mean.append(round(mean(f1_gan),2))
        gan_stdev.append(round(stdev(f1_gan),2))
        esmote_mean.append(round(mean(f1_esmote),2))
        esmote_stdev.append(round(stdev(f1_esmote),2))
    
    no_preprocess = []
    smote = []
    gan = []
    esmote = []
    for i in range(len(no_preprocess_mean)):
        no_preprocess.append(f"{no_preprocess_mean[i]} +- {no_preprocess_stdev[i]}")
        smote.append(f"{smote_mean[i]} +- {smote_stdev[i]}")
        gan.append(f"{gan_mean[i]} +- {gan_stdev[i]}")
        esmote.append(f"{esmote_mean[i]} +- {esmote_stdev[i]}")
    
    data = {'Data': data_names,
            'No preprocess': no_preprocess,
            'SMOTE': smote,
            'GAN': gan,
            'ESMOTE': esmote}
    df = pd.DataFrame(data)
    df.to_csv(f'{concept_drift_type}.csv', index=False)  
