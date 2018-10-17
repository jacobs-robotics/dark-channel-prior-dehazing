#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Implementation for Single Image Haze Removal Using Dark Channel Prior.

Reference:
http://research.microsoft.com/en-us/um/people/kahe/cvpr09/
http://research.microsoft.com/en-us/um/people/kahe/eccv10/
"""

import numpy as np
from PIL import Image
from PIL import ImageFilter

from guidedfilter import guided_filter

R, G, B = 0, 1, 2  # index for convenience
max_color_val = 256  # color depth


def get_dark_channel(I, w):
    """Get the dark channel prior in the (RGB) image data.

    Parameters
    -----------
    I:  an M * N * 3 numpy array containing data ([0, max_color_val-1]) in the image where
        M is the height, N is the width, 3 represents R/G/B channels.
    w:  window size

    Return
    -----------
    An M * N array for the dark channel prior ([0, max_color_val-1]).
    """
    M, N, _ = I.shape
    padded = np.pad(I, ((w / 2, w / 2), (w / 2, w / 2), (0, 0)), 'edge')
    dark_ch = np.zeros((M, N))
    ##NOTE:Choose the minimum pixel value in the window
    for i, j in np.ndindex(dark_ch.shape):
        ##NOTE:If no axis is given for he minimum, the array is flattened
        ##NOTE: CVPR09, eq.5
        dark_ch[i, j] = np.min(padded[i:i + w, j:j + w, :])
    return dark_ch


def get_atmosphere(I, dark_ch, p):
    """Get the atmosphere light in the (RGB) image data.

    Parameters
    -----------
    I:       the M * N * 3 RGB image data ([0, max_color_val-1]) as numpy array
    dark_ch: the dark channel prior of the image as an M * N numpy array
    p:       percentage of pixels for estimating the atmosphere light

    Return
    -----------
    A 3-element array containing atmosphere light ([0, max_color_val-1]) for each channel
    """
    ##NOTE: CVPR09, eq. 4.4
    M, N = dark_ch.shape
    flat_I = I.reshape(M * N, 3)
    flat_dark = dark_ch.ravel()
    ##NOTE: Find top M * N * p indexes
    search_idx = (-flat_dark).argsort()[:int(M * N * p)]
    #print 'atmosphere light region:', [(i / N, i % N) for i in search_idx] #DEBUGGING LINE

    ##NOTE: Return the highest intensity for each channel
    return np.max(flat_I.take(search_idx, axis=0), axis=0)


def get_transmission(I, A, omega, w):
    """Get the transmission esitmate in the (RGB) image data.

    Parameters
    -----------
    I:       the M * N * 3 RGB image data ([0, max_color_val-1]) as numpy array
    A:       a 3-element array containing atmosphere light
             ([0, max_color_val-1]) for each channel
    omega:   bias for the estimate
    w:       window size for the estimate

    Return
    -----------
    An M * N array containing the transmission rate ([0.0, 1.0])
    """
    return 1 - omega * get_dark_channel(I / A, w)  # CVPR09, eq.12


def dehaze_raw(I, t_min=0.2, atm_max=220, w=15, p=0.0001,
               omega=0.95, guided=True, r=40, eps=1e-3):
    """Get the dark channel prior, atmosphere light, transmission rate
       and refined transmission rate for raw RGB image data.

    Parameters
    -----------
    I:      M * N * 3 data as numpy array for the hazy image
    t_min:  threshold of transmission rate
    atm_max:threshold of atmosphere light
    w:      window size of the dark channel prior
    p:      percentage of pixels for estimating the atmosphere light
    omega:  bias for the transmission estimate

    guided: whether to use the guided filter to fine the image
    r:      the radius of the guidance
    eps:    epsilon for the guided filter

    Return
    -----------
    (Idark, A, rawt, refinedt) if guided=False, then rawt == refinedt
    """
    
    ##>ONLY FOR UNDERWATER IMAGES
    # Iuw = np.zeros(I.shape,dtype=np.float64)
    # Iuw[:,:,0] = 255. - I[:,:,0]
    # Iuw[:,:,1] = 255. - I[:,:,1]
    # Iuw[:,:,2] = I[:,:,2]
    # Idark = get_dark_channel(Iuw, w)

    ##NOTE:First, get dark channel image. 
    Idark = get_dark_channel(I, w)

    ##NOTE:Estimate the atmospheric light
    atm_light = get_atmosphere(I, Idark, p)
    atm_light = np.minimum(atm_light, atm_max)
    print 'atmosphere', atm_light

    ##NOTE:Estimate transmission image which correlates to depth
    rawt = get_transmission(I, atm_light, omega, w)
    #For uw image
    #rawt = get_transmission(Iuw, A, Idark, omega, w)
    print 'raw transmission rate',
    print 'between [%.4f, %.4f]' % (rawt.min(), rawt.max())

    ##NOTE: Refine transmission rate through guided filter (edge-preserving filter)
    rawt = refinedt = np.maximum(rawt, t_min)
    if guided:
        normI = (I - I.min()) / (I.max() - I.min())
        refinedt = guided_filter(normI, refinedt, r, eps)

    print 'refined transmission rate',
    print 'between [%.4f, %.4f]' % (refinedt.min(), refinedt.max())

    return Idark, atm_light, rawt, refinedt


def get_radiance(I, atm_light, trans):
    """Recover the radiance from raw image data with atmosphere light
       and transmission rate estimate.

    Parameters
    ----------
    I:              M * N * 3 data as numpy array for the hazy image
    atm_light:      a 3-element array containing atmosphere light
                    ([0, max_color_val-1]) for each channel
    trans:          estimate fothe transmission rate

    Return
    ----------
    M * N * 3 numpy array for the recovered radiance
    """

    ##NOTE: Tile transmission image
    tiledt = np.zeros_like(I)
    tiledt[:, :, R] = tiledt[:, :, G] = tiledt[:, :, B] = trans

    #im_depth = Image.open('/home/arturokkboss33/code_projects/dark-channel-prior-dehazing/img/panel_sim_1_depth.jpg')
    #im_depth = im_depth1.filter(ImageFilter.GaussianBlur(5))
    #im_gray = im_depth.convert("L")
    #Idepth = np.asarray(im_gray,dtype=np.float64)
    #attenuation_coeff = 0.5
    #Idepth = np.maximum(Idepth,0.0001)
    #Idepth = np.exp(-attenuation_coeff*Idepth)
    #print("aaaa")
    #print(np.max(Idepth))
    #print(np.min(Idepth))
    #tiledt[:, :, R] = tiledt[:, :, G] = tiledt[:, :, B] = Idepth

    ##NOTE: CVPR09, eq.16
    return (I - atm_light) / tiledt + atm_light


def to_img(raw):
    ##NOTE: Threshold image to be in the range 0 - max_color_val-1
    cut = np.maximum(np.minimum(raw, max_color_val - 1), 0).astype(np.uint8)

    return Image.fromarray(cut)

def dehaze(img, t_min=0.2, atm_max=220, w=15, p=0.0001,
           omega=0.95, guided=True, r=40, eps=1e-3):
    """Dehaze the given RGB image.

    Parameters
    ----------
    img:     the Image object of the RGB image
    guided: refine the dehazing with guided filter or not
    other parameters are the same as `dehaze_raw`

    Return
    ----------
    (dark, rawt, refinedt, rawrad, rerad)
    Images for dark channel prior, raw transmission estimate,
    refiend transmission estimate, recovered radiance with raw t,
    recovered radiance with refined t.
    """
    
    I = np.asarray(img, dtype=np.float64)
    Idark, atm_light, rawt, refinedt = dehaze_raw(I, t_min, atm_max, w, p,
                                          omega, guided, r, eps)
    white = np.full_like(Idark, max_color_val - 1)

    return [to_img(raw) for raw in (Idark, white * rawt, white * refinedt,
                                    get_radiance(I, atm_light, rawt),
                                    get_radiance(I, atm_light, refinedt))]
