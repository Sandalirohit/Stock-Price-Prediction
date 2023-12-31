

#importing libraries
import numpy as np 
import csv 
import os, sys
from pathlib import Path, PureWindowsPath

#getting data
from pandas_datareader import data as pdr
from datetime import datetime

#data processing
import pandas as pd 
pd.set_option('display.max_columns', 25)

#data visualization
import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib import style

#for normalizing data
from sklearn.preprocessing import MinMaxScaler

#For Statistics
from sklearn.metrics import r2_score

#avoid warnings
import warnings
warnings.filterwarnings('ignore')

#to create nueral network
from keras.models import Sequential
from keras.layers import Dense, Dropout, LSTM

#setting the seed
import random
np.random.seed(1234)
import tensorflow as tf
#tf.set_random_seed(1000)
tf.random.set_seed(1000)

#this funtion builds our LSTM model
def build_model(train,valid,new_data,scaler,params,
                scaled_data_train,scaled_data_valid):    
    
    #creating the training set in the required format
    #we will put together 60 days (offset) of data together and treat that as single input 
    #and the target value is the 'Close' price on the next day
    x_train, y_train = [], []
    for i in range(params['offset'],len(train)):
        x_train.append(scaled_data_train[i-params['offset']:i,0])
        y_train.append(scaled_data_train[i,0])
        
    x_train, y_train = np.array(x_train), np.array(y_train)
    x_train = np.reshape(x_train, (x_train.shape[0],x_train.shape[1],1))
    
    #scale = MinMaxScaler(feature_range=(0,1))
    #scale.min_, scale.scale_ = scaler.min_, scaler.scale_
    
    #creating a new dataframe which will be used to create the test set
    inputs = new_data[len(new_data) - len(valid) - params['offset']:].values
    inputs = inputs.reshape(-1,1)
    inputs = scaler.transform(inputs)
    
    X_test, Y_test = [], []
    for i in range(params['offset'],inputs.shape[0]):
        X_test.append(inputs[i-params['offset']:i,0])
        Y_test.append(inputs[i,0])
        
    X_test, Y_test = np.array(X_test), np.array(Y_test)
    X_test = np.reshape(X_test, (X_test.shape[0],X_test.shape[1],1))    
    
    #create and fit the LSTM network
    #we are building a general model here. This section of code will be used in further steps
    #where we will check if only 1 hidden layer can give better results
    #so an if-else loop is created to combat that situaiton
    if (params['units_2']):
        
        model = Sequential()
        model.add(LSTM(units=params['units_1'], return_sequences=True, 
                       input_shape=(x_train.shape[1],1)))
        model.add(Dropout(rate=params['drop_rate_1']))
        model.add(LSTM(units=params['units_2']))
        model.add(Dropout(rate=params['drop_rate_2']))
        model.add(Dense(1)) 
        
    else:
        
        model = Sequential()
        model.add(LSTM(units=params['units_1'], return_sequences=False, 
                       input_shape=(x_train.shape[1],1)))
        model.add(Dropout(rate=params['drop_rate_1']))
        model.add(Dense(1))
    
    model.compile(loss='mean_squared_error', optimizer='adam')
    history = model.fit(x_train, y_train, epochs=params['epochs'], verbose=1,
                        batch_size=params['batch_size'], 
                        validation_data=[X_test, Y_test])
    
    return model, history, X_test


#predicting our model accuracy
def get_accuracy(train,valid,new_data,tl, 
                 scaler,model,X_test):
    
    closing_price = model.predict(X_test)
    closing_price = scaler.inverse_transform(closing_price)
    
    train = new_data[:tl]
    valid = new_data[tl:]
    valid['Predictions'] = closing_price
    
    #for plotting
    plt.figure(figsize=(16,8))
    plt.plot(train['Close'])
    plt.plot(valid['Close'], label='Actual Close Price')
    plt.plot(valid['Predictions'] , label='Predicted Close Price')
    plt.legend()
    
    #RMS error
    rms = np.sqrt(np.mean(np.power((valid-closing_price),2)))
    
    #R-squared
    y_true = valid['Close']
    y_pred = valid['Predictions']
    r = r2_score(y_true, y_pred)
    
    return rms[0], r  
   

def run(data_df, params):    
    
    #Plot the data and check if there are any unexpected anamolies(sudden spikes or dips)
    plt.figure(figsize=(16,8))
    plt.plot(data_df['Close'], label='Close Price history')
    plt.title('Close Price History')
    
    #In our model, we will try to predict the future close price of a stock using only the past
    #close prices of that particular stock. So let's a create a new dataframe with only the
    #'Date' and 'Close' price columns
    new_data = pd.DataFrame(index=range(0,len(data_df)),columns=['Date', 'Close'])
    for i in range(0,len(data_df)):
        new_data['Date'][i]  = data_df.index[i]
        new_data['Close'][i] = data_df['Close'][i]
        
    #setting 'Date' column as index and dropping the original column
    new_data.index = new_data.Date
    new_data.drop('Date', axis=1, inplace=True)
    
    #80% of the data is used as training set and 20% as test set
    #'test set' here is referred to as 'validatation set'
    #'tl' stands for 'train length'
    frac = 0.8
    tl = int(len(new_data)*frac)
    
    dataset = new_data.values
    train = dataset[0:tl,:]
    valid = dataset[tl:,:]
    
    #Normalizing the data
    scaler = MinMaxScaler(feature_range=(0,1))
    scaler.fit(train)
    scaled_data_train = scaler.transform(train)
    scaled_data_valid = scaler.transform(valid)
    
    #building the LSTM model
    model, history, X_test = build_model(train,valid,new_data,scaler,params,
                                         scaled_data_train,scaled_data_valid)
    
    #getting the 'RMSE error' and 'R-squared value'
    rms, r = get_accuracy(train,valid,new_data,tl,
                          scaler,model,X_test)
    
    #Conveting the params in dictionary to dataframe, to store all the data
    params_items = params.items()
    params_list  = list(params_items)    
    params_df = pd.DataFrame(params_list, index=params.keys())
    
    #Adding errors to the above dataframe    
    errors = {'RMS': rms,
              'R-square':r}
    errors_items = errors.items()
    errors_list  = list(errors_items)    
    errors_df = pd.DataFrame(errors_list, index=errors.keys())
    
    result_df = pd.concat([params_df,errors_df])
    result_df = result_df.drop([0], axis=1)
    
    return result_df



#'main' program
if __name__ == '__main__':

    #data_df = pd.read_csv('GOOG_2015-04-01_2020-03-31.csv', index_col='Date', parse_dates=True)
    #using pandas_datareader library to get the data from Yahoo-Finance
    start_date = datetime(2015, 4, 1)
    end_date   = datetime(2020, 3, 31)
    ticker = 'GOOG'
    
    data_df = pdr.get_data_yahoo(tickers=ticker, start=start_date, end=end_date)
    #saving this as .csv file for future use
    filename = ticker+'_'+str(start_date.date())+'_'+str(end_date.date())
    filename = filename+'.csv'
    data_df.to_csv(filename, index = True, header = True)
    
    #Defining the initial parameters of the model
    #These parameters are chosen random and will be adjusted till this model
    #gets an accuracy of more than 90%    
    params = {'offset':60,
              'units_1':32,
              'drop_rate_1':0,
              'units_2':32,
              'drop_rate_2':0,
              'batch_size':5,
              'epochs':10}    

    result_df = run(data_df, params)
    
    #Printing the params and errors
    print(result_df)
      