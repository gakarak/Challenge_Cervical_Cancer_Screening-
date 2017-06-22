#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'ar'

import time
import shutil
import os
import math
import matplotlib.pyplot as plt
import skimage.io as skio
import skimage.transform as sktf
import skimage.exposure as skexp
import numpy as np
import keras
from keras.layers import Conv2D, UpSampling2D, \
    Flatten, Activation, Reshape, MaxPooling2D, Input, merge
from keras.models import Model
import keras.losses
import keras.callbacks as kall
import pandas as pd

from keras.preprocessing.image import ImageDataGenerator
from keras.utils.vis_utils import plot_model as kplot
from keras.utils import np_utils
from keras.utils.vis_utils import plot_model

#####################################################
def buildModelFCNN_UpSampling2D(inpShape=(256, 256, 3), numCls=2, kernelSize=3, numFlt = 8):
    dataInput = Input(shape=inpShape)
    # -------- Encoder --------
    # Conv #1
    conv1 = Conv2D(filters= numFlt * (2**0), kernel_size=(kernelSize,kernelSize),
                   padding='same', activation='relu')(dataInput)
    pool1 = MaxPooling2D(pool_size=(2,2))(conv1)
    # Conv #2
    conv2 = Conv2D(filters= numFlt * (2**1), kernel_size=(kernelSize, kernelSize),
                   padding='same', activation='relu')(pool1)
    pool2 = MaxPooling2D(pool_size=(2, 2))(conv2)
    # Conv #3
    conv3 = Conv2D(filters= numFlt * (2**2), kernel_size=(kernelSize, kernelSize),
                   padding='same', activation='relu')(pool2)
    pool3 = MaxPooling2D(pool_size=(2, 2))(conv3)
    # Conv #4
    conv4 = Conv2D(filters= numFlt * (2**3), kernel_size=(kernelSize, kernelSize),
                   padding='same', activation='relu')(pool3)
    pool4 = MaxPooling2D(pool_size=(2, 2))(conv4)
    # Conv #5
    conv5 = Conv2D(filters= numFlt * (2**4), kernel_size=(kernelSize, kernelSize),
                   padding='same', activation='relu')(pool4)
    pool5 = MaxPooling2D(pool_size=(2, 2))(conv5)
    #
    # -------- Decoder --------
    # UpConv #1
    upconv1 = Conv2D(filters= numFlt * (2**4), kernel_size=(kernelSize, kernelSize),
                     padding='same', activation='relu')(pool5)
    up1 = keras.layers.concatenate([UpSampling2D(size=(2, 2))(upconv1),conv5], axis=-1)
    # UpConv #2
    upconv2 = Conv2D(filters= numFlt * (2**3), kernel_size=(kernelSize, kernelSize),
                     padding='same', activation='relu')(up1)
    up2 = keras.layers.concatenate([UpSampling2D(size=(2, 2))(upconv2), conv4], axis=-1)
    # UpConv #3
    upconv3 = Conv2D(filters= numFlt * (2**2), kernel_size=(kernelSize, kernelSize),
                     padding='same', activation='relu')(up2)
    up3 = keras.layers.concatenate([UpSampling2D(size=(2, 2))(upconv3), conv3], axis=-1)
    # UpConv #4
    upconv4 = Conv2D(filters= numFlt * (2**1), kernel_size=(kernelSize, kernelSize),
                     padding='same', activation='relu')(up3)
    up4 = keras.layers.concatenate([UpSampling2D(size=(2, 2))(upconv4), conv2], axis=-1)
    # UpConv #5
    upconv5 = Conv2D(filters= numFlt * (2**0), kernel_size=(kernelSize, kernelSize),
                     padding='same', activation='relu')(up4)
    up5 = keras.layers.concatenate([UpSampling2D(size=(2, 2))(upconv5), conv1], axis=-1)
    #
    # 1x1 Convolution: emulation of Dense layer
    convCls = Conv2D(filters=numCls, kernel_size=(1,1), padding='valid', activation='linear')(up5)
    # sizeReshape = np.prod(inpShape[:2])
    ret = Reshape([-1, numCls])(convCls)
    ret = Activation('softmax')(ret)
    retModel = Model(dataInput, ret)
    return retModel

#####################################################
def buildModelFCNN_UpSampling2D_V2(inpShape=(384, 384, 3), numCls=2, numConv=2, kernelSize=3, numFlt=8, ppad='same', numSubsampling=6, isDebug=False):
    dataInput = Input(shape=inpShape)
    fsiz = (kernelSize, kernelSize)
    psiz = (2, 2)
    x = dataInput
    # -------- Encoder --------
    lstMaxPools = []
    for cc in range(numSubsampling):
        for ii in range(numConv):
            x = Conv2D(filters=numFlt * (2**cc), kernel_size=fsiz, padding=ppad, activation='relu')(x)
        lstMaxPools.append(x)
        x = MaxPooling2D(pool_size=psiz)(x)
    # -------- Decoder --------
    for cc in range(numSubsampling):
        for ii in range(numConv):
            x = Conv2D(filters=numFlt * (2 ** (numSubsampling - 1 -cc)), kernel_size=fsiz, padding=ppad, activation='relu')(x)
        x = UpSampling2D(size=psiz)(x)
        # if cc< (numSubsampling-1):
        #     x = keras.layers.concatenate([x, lstMaxPools[-1 - cc]], axis=-1)
        x = keras.layers.concatenate([x, lstMaxPools[-1 - cc]], axis=-1)
    #
    # 1x1 Convolution: emulation of Dense layer
    x = Conv2D(filters=numCls, kernel_size=(1,1), padding='valid', activation='linear')(x)
    x = Reshape([-1, numCls])(x)
    x = Activation('softmax')(x)
    retModel = Model(dataInput, x)
    if isDebug:
        retModel.summary()
        fimg_model = 'model_graph_FCNN_UpSampling2D_V2.png'
        kplot(retModel, fimg_model, show_shapes=True)
        plt.imshow(skio.imread(fimg_model))
        plt.show()
    return retModel

#####################################################
def readDataAsList(pidx, wdir=None, numCls=2):
    if wdir is None:
        wdir = os.path.dirname(pidx)
    lstpath = pd.read_csv(pidx)['path'].as_matrix()
    lstpath = [os.path.join(wdir,xx) for xx in lstpath]
    numPath = len(lstpath)
    dataX = []
    dataY = []
    print (':: readDataAsList()')
    for ii,pp in enumerate(lstpath):
        img4 = skio.imread(pp)
        img = (img4[:, :, :3].astype(np.float32) / 127.5) - 1.0
        if img4.ndim>2:
            msk = (img4[:, :, -1]>200).astype(np.float32)
            msk = np_utils.to_categorical(msk.reshape(-1), numCls)
            msk = msk.reshape(list(img.shape[:2]) + [numCls])
        else:
            msk = None
        dataX.append(img)
        dataY.append(msk)
        if (ii%100)==0:
            print ('\t[%d/%d] ...' % (ii, numPath))
    return (dataX, dataY, lstpath)

def readDataImages(pidx, wdir=None):
    if wdir is None:
        wdir = os.path.dirname(pidx)
    dataY   = pd.read_csv(pidx)['type'].as_matrix() - 1
    lstpath = pd.read_csv(pidx)['path'].as_matrix()
    lstpath = [os.path.join(wdir, xx) for xx in lstpath]
    numPath = len(lstpath)
    dataX = None
    # dataX = []
    print (':: read images into memory...')
    for ipath, path in enumerate(lstpath):
        timg = skio.imread(path)
        if dataX is None:
            dataX = np.zeros([numPath] + list(timg.shape))
        if (ipath%20)==0:
            print ('\t[{0}/{1}]'.format(ipath, numPath))
        dataX[ipath] = timg
        # dataX.append(timg)
    return dataX#, dataY

def readDataVal(pidx, wdir=None, numCls=2, cropSize=(256,256)):
    lstX, lstY, _ = readDataAsList(pidx, wdir=wdir, numCls=numCls)
    numImg = len(lstX)
    dataX = None
    dataY = None
    for ii in range(numImg):
        tsize = lstX[ii].shape[:2][::-1]
        tx, ty = np.where(lstY[ii][:,:,1])
        cx = int(np.mean(tx))
        cy = int(np.mean(ty))
        px1 = cx - cropSize[0] / 2
        py1 = cy - cropSize[1] / 2
        if px1 < 0:
            px1 = 0
        if py1 < 0:
            py1 = 0
        if px1 + cropSize[0]>=tsize[0]:
            px1 = tsize[0] - cropSize[0]
        if py1 + cropSize[1] >= tsize[1]:
            py1 = tsize[1] - cropSize[1]
        timg = lstX[ii][py1:py1 + cropSize[1], px1:px1 + cropSize[0], :].copy()
        tmsk = lstY[ii][py1:py1 + cropSize[1], px1:px1 + cropSize[0], :].copy()
        if dataX is None:
            dataX = np.zeros([numImg] + list(cropSize) + [3], dtype=np.float32)
            # dataY = np.zeros([numImg] + list(cropSize) + [numCls], dtype=np.float32)
            dataY = np.zeros([numImg] + [np.prod(cropSize), numCls], dtype=np.float32)
        dataX[ii] = timg
        dataY[ii] = tmsk.reshape([-1, numCls])
    return (dataX, dataY)

#####################################################
def _getRand():
    return 2. * (np.random.rand() - 0.5)

def preproc_image(pimg, prnd=None):
    prnd = 2
    ndim = pimg.ndim
    if prnd is None:
        trnd = np.random.randint(4)
    else:
        trnd = prnd
    # trnd = 1
    timg = pimg[:, :, :3].copy()
    tmsk = pimg[:, :,  3].copy()
    ret = pimg.copy()
    if trnd == 0:
        timg = skexp.equalize_hist(timg.astype(np.uint8), mask=tmsk).astype(np.float32) * 255.
    elif trnd == 1:
        vrnd = 1.0 + 0.2 * ( np.random.rand() - 0.5)
        timg = skexp.adjust_gamma(timg, vrnd, 2.71828 / np.exp(vrnd))
    elif trnd > 1:
        rndVals = 2.0 * np.random.rand(ndim,2) - 1.0
        rndVals[:, 0] *= 30
        rndVals[:, 1] = 1.0 + 0.2 * rndVals[:, 1]
        for ii in range(ndim):
            timg[:,:,ii] = rndVals[ii,0] + rndVals[ii,1] * timg[:,:,ii]
    timg[timg < 0] = 0
    timg[timg > 255] = 255
    timg[tmsk < 1] = 0
    ret[:, :,:3] = timg.copy()
    ret[:, :, 3] = tmsk.copy()
    return ret

def train_generator(dataImg, pdataGenerator, numCls=2, batchSize=64, numRandGenPerBatch=16, imsize = 256, isRandomize=True):
    numImg   = dataImg.shape[0]
    shapeMsk = dataImg.shape[1:3]
    shapeMskCat = list(shapeMsk) + [numCls]
    imgIdx = list(range(numImg))
    dataGeneratorFlow = pdataGenerator.flow(dataImg, None, batch_size=numRandGenPerBatch)
    while True:
        if isRandomize:
            dataImgG = next(dataGeneratorFlow)
        else:
            rndIdx = np.random.permutation(imgIdx)[:numRandGenPerBatch]
            dataImgG = dataImg[rndIdx].copy()
        # shape of data-generator can be changed and not equal [batchSize] !!!
        numRandGenPerBatchReal = dataImgG.shape[0]
        dataX = np.zeros((batchSize, imsize, imsize, 3))
        dataY = np.zeros((batchSize, imsize * imsize, numCls))
        numSampleData = int(math.ceil(float(batchSize) / numRandGenPerBatchReal))
        tcnt = 0
        tcntImg = 0
        rndRR = np.random.randint(0, shapeMsk[0] - imsize - 1, batchSize)
        rndCC = np.random.randint(0, shapeMsk[1] - imsize - 1, batchSize)
        while tcnt < batchSize:
            timg = dataImgG[tcntImg][:, :, :3] / 127.5 - 1.0
            tmsk = np_utils.to_categorical((dataImgG[tcntImg][:, :, 3] > 100).reshape(-1), numCls).reshape(shapeMskCat)
            for ii in range(numSampleData):
                trr = rndRR[tcnt]
                tcc = rndCC[tcnt]
                dataX[tcnt] = timg[trr:trr + imsize, tcc:tcc + imsize, :].copy()
                dataY[tcnt] = tmsk[trr:trr + imsize, tcc:tcc + imsize, :].reshape(-1, numCls).copy()
                tcnt += 1
            tcntImg +=1
        # print ('-')
        yield (dataX, dataY)

#####################################################
if __name__ == '__main__':
    isDebug = False
    # buildModelFCNN_UpSampling2D_V2(isDebug=True)
    # (1) Setup Tran/Validation data
    fidxTrn = '/home/ar/data/@Kaggle/01_Intel_&_MobileODT_Cervical_Cancer_Screening/data/train-x512-processed-stage2/01-data-512x512/idx.txt-train.txt'
    fidxVal = '/home/ar/data/@Kaggle/01_Intel_&_MobileODT_Cervical_Cancer_Screening/data/train-x512-processed-stage2/01-data-512x512/idx.txt-val.txt'
    wdir = os.path.dirname(fidxTrn)
    #
    pathImgs = pd.read_csv(fidxTrn)['path'].as_matrix()
    pathImgs = np.array([os.path.join(wdir, xx) for xx in pathImgs])
    # (2) Input/Output models
    pathModelValLoss = '{0}/model_fcn_cervix_valLoss_v2.h5'.format(wdir)
    pathModelValAcc = '{0}/model_fcn_cervix_valAcc_v2.h5'.format(wdir)
    pathModelLatest = '{0}/model_fcn_cervix_Latest_v2.h5'.format(wdir)
    pathLog = '%s-log.csv' % pathModelValLoss
    # (3) Visualise model (for test)
    #
    # (4) Continue training from checkpoint Model (if exists)
    pathModelRestart = pathModelValLoss
    if not os.path.isfile(pathModelRestart):
        # model = buildModelFCNN_UpSampling2D()
        model = buildModelFCNN_UpSampling2D_V2(numSubsampling=5, numFlt=8, isDebug=isDebug)
        model.compile(optimizer='adam',
                      loss='categorical_crossentropy',
                      metrics=['accuracy'])
    else:
        pref = time.strftime('%Y.%m.%d-%H.%M.%S')
        pathModelValBk = '%s-%s.bk' % (pathModelValLoss, pref)
        pathModelValAccBk = '%s-%s.bk' % (pathModelValAcc, pref)
        pathModelLatestBk = '%s-%s.bk' % (pathModelLatest, pref)
        shutil.copy(pathModelValLoss, pathModelValBk)
        shutil.copy(pathModelValAcc, pathModelValAccBk)
        # shutil.copy(pathModelLatest, pathModelLatestBk)
        model = keras.models.load_model(pathModelRestart)
    # (5) Preload data
    numTrn = len(pd.read_csv(fidxTrn))
    numVal = len(pd.read_csv(fidxVal))
    #
    dataGenerator = ImageDataGenerator(
        zoom_range=[1.0, 1.3],
        width_shift_range=0.1,
        height_shift_range=0.1,
        rotation_range=16,
        horizontal_flip=True,
        fill_mode='constant',
        cval=0,
        preprocessing_function=preproc_image
    )
    dataTrn = readDataImages(fidxTrn, wdir=wdir)
    dataVal = readDataImages(fidxVal, wdir=wdir)
    #
    imgSize = 384
    batchSize = 32
    numEpochs = 1000
    numIterPerEpoch = numTrn / batchSize
    # dataTrn = dataVal
    valX, valY = next(train_generator(dataImg=dataVal,
                                      pdataGenerator=dataGenerator,
                                      imsize=imgSize,
                                      batchSize=1024,
                                      numRandGenPerBatch=4,
                                      isRandomize=False))
    #
    model.fit_generator(
        generator=train_generator(dataTrn, pdataGenerator=dataGenerator, imsize=imgSize, batchSize=batchSize, numRandGenPerBatch=2, isRandomize=True),
        steps_per_epoch=numIterPerEpoch,
        epochs=numEpochs,
        validation_data=(valX, valY),
        callbacks=[
            kall.ModelCheckpoint(pathModelValLoss, verbose=True, save_best_only=True, monitor='val_loss'),
            kall.ModelCheckpoint(pathModelValAcc, verbose=True, save_best_only=True, monitor='val_acc'),
            # kall.ModelCheckpoint(pathModelLatest, verbose=True, save_best_only=False),
            kall.CSVLogger(pathLog, append=True)
        ])