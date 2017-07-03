#!/usr/bin/python
# -*- coding:UTF-8 -*-
"""
通过我们的比对文件，以及自己生成的参考集，计算Aneuploidy(非整倍体)情况
输入文件有:
    *.gz.20K.GC.txt
    *.gz.20K.txt
    自制参考集:
        等价与Increment中winRatio_50k参考集
        正常样本计算的染色体PZ值均值与方差
"""

import pandas as pd
import glob
import pickle
import math
import numpy as np

def read_file(
        sample,\
        dirname='./',\
        rd_file_ext='gz.20K.txt',\
        gc_file_ext='gz.20K.GC.txt'\
        ):
    """
    读取比对原始文件，返回需要的变量
    sample:
        选取的样本
    dirname:
        文件目录
    rd_file_ext:
        rd文件后缀
    gc_file_ext:
        gc文件后缀
    """
    print "Handling %s....." % sample
    rd_file_regx = "%s/%s*.%s" % (dirname, sample, rd_file_ext)
    try:
        rd_file = glob.glob(rd_file_regx)[0]
    except IndexError,e:
        print rd_file_regx,"没有找到文件", e
        return
    gc_file_regx = "%s/%s*.%s" % (dirname, sample, gc_file_ext)
    try:
        gc_file = glob.glob(gc_file_regx)[0]
    except IndexError,e:
        print gc_file_regx, "没有找到文件", e
        return
    rd = pd.read_csv(rd_file, comment="#", index_col=0, sep="\t", header=None)
    gc = pd.read_csv(gc_file, comment="#", index_col=0, sep="\t", header=None)
    gc_per = gc/(rd*36)
    gc_per[gc_per.isnull()] = -1
    return rd, gc_per

def read_win_ref(ref_file, dirname="./", chromlist=range(1,23)):
    """
    读取自建的increment参考集文件，并生成一个字典，键结构如下:
        chrom:
            start:
                end
                w_gc
                w_coe
                w_sd
    ref_file:
        参考集文件名
    dirname:
        参考集存放路径
    chromlist:
        感兴趣染色体列表
    """
    try:
        refdata = pd.read_csv("%s/%s"%(dirname, ref_file), sep="\t")
    except:
        print "解析%s/%s时出错"%(dirname,ref_file)
    refdict = {}
    for i,data in refdata.iterrows(): # 按行读取矩阵
        chrom = int(float(data['chr']))
        if (not chrom in chromlist): continue
        start = int(float(data['start']))
        innerdict = {'end': int(float(data['end'])), 'w_gc': data['gc'], 'w_coe': data['ratio'], 'w_sd': data['sd']}
        if refdict.has_key(chrom):
            refdict[chrom][start] = innerdict
        else:
            refdict[chrom] = {start: innerdict}
    return refdict
def read_zscore_ref(ref_file, dirname="./", chromlist=range(1,23)):
    """
    读取zscore参考集文件，获得每个染色体pz值的均值方差
    """
    filename = "%s/%s"%(dirname,ref_file)
    try:
        refdata = pd.read_csv(filename, sep="\t",index_col=0, skiprows=lambda x: (x!=201 and x!=0 and x!=202))
    except:
        print "解析%s/%s时出错"%(dirname,ref_file)
    refdict = {}
    for i,data in refdata.iterrows():
        for key, value  in data.to_dict().iteritems():
            key = int(key)
            if refdict.has_key(key):
                refdict[key][i] = value
            else:
                refdict[key] = {i:value}
    return refdict

if __name__=='__main__':
    samplefile = "p-sample.list"
    samplelist = pd.read_csv(samplefile, header=None)
    #input_dir = "/home/bixichao/Projects/tmp/Increment/mapping"
    input_dir = "./test-pathosis"
    ref_file = "ref"
    ref_dir = "./"
    zscore_ref_file = "zscore"
    chromlist = range(1,23)
    refdict = read_win_ref(ref_file, chromlist = chromlist, dirname=ref_dir)
    zscoreref = read_zscore_ref(zscore_ref_file, ref_dir)
    for sample in samplelist.values:
        (rd, gc_per) = read_file(sample[0], input_dir)
        get = (gc_per > 0) & (rd > 0)
        rd_get = rd[get]
        gc_per_get = gc_per[get]
        gc2rd = {}
        for index in rd_get.columns:
            pos = 20000*(index-1) + 1
            for chrom in chromlist:
                if refdict[chrom].has_key(pos):
                    if math.isnan(rd_get[index]["chr%d"%chrom]):
                        refdict[chrom][pos]['rc'] = 1
                        refdict[chrom][pos]['gc'] = float("%.3f"%refdict[chrom][pos]['w_gc'])
                    else:
                        key = "%.3f"%gc_per_get[index]["chr%d"%chrom]
                        refdict[chrom][pos]['rc'] = int(rd_get[index]["chr%d"%chrom])
                        refdict[chrom][pos]['gc'] = float(key)
                        if gc2rd.has_key(key):
                            gc2rd[key].append(int(rd_get[index]["chr%d"%chrom]))
                        else:
                            gc2rd[key] = [int(rd_get[index]["chr%d"%chrom])]
        #with open("refdict",'w') as f: pickle.dump(refdict,f)
        #with open("gc2rd",'w') as f: pickle.dump(gc2rd,f)
        # remove window when rc less than 11
        for key in gc2rd.keys():
            if len(gc2rd[key]) < 10: gc2rd.pop(key)
        # calculate correction coefficent
        all_median = np.median(sum(gc2rd.values(),[]))
        gc_rectify = {}
        for key,value in gc2rd.iteritems():
            gc_rectify[key] = all_median/np.median(value)
            if gc_rectify[key] > 2 or gc_rectify[key] < 0.4:
                gc_rectify[key] = 1
        # rectify the windows by gc
        total_read = {}
        for chrom in refdict.keys():
            total_read[chrom] = 0
            for pos in refdict[chrom].keys():
                gckey = "%.3f"%refdict[chrom][pos]['gc']
                if gc_rectify.has_key(gckey):
                    refdict[chrom][pos]['rc'] *= gc_rectify[gckey]
                total_read[chrom] += refdict[chrom][pos]['rc']
        # get all rd
        rd_stats = {}
        for chrom in refdict.keys():
            rd_stats[chrom] = {'ratio':[],'sd':[]}
            for pos in refdict[chrom].keys():
                rc = refdict[chrom][pos]['rc']
                coe = refdict[chrom][pos]['w_coe']
                sd = refdict[chrom][pos]['w_sd']
                percent = float("%.3f"%(rc/(sum(total_read.values())*coe)))
                rd_stats[chrom]['ratio'].append(percent)
                rd_stats[chrom]['sd'].append(sd)

        #with open("rd_stats",'w') as f: pickle.dump(rd_stats,f)
        all_ratio = sum(map(lambda x: rd_stats[x]['ratio'],rd_stats.keys()),[])
        t_mean = np.mean(all_ratio)
        t_sd = np.std(all_ratio)
        # zscore
        with open("%s/%s.zscore"%(input_dir,sample[0]),'w') as f:
            f.write("chr\tRatioMean\tSZ\tPZ\n")
            for chrom in chromlist:
                ratios = rd_stats[chrom]['ratio']
                sds = rd_stats[chrom]['sd']
                mean = np.mean(ratios)
                sd = np.std(sds)
                sz = (mean - t_mean)/t_sd
                pz = (mean - 1)/sd
                f.write("%d\t%.3f\t%.3f\t%.3f\n"%(chrom,mean,sz,pz))
                #print "%d\t%.3f\t%.3f\t%.3f"%(chrom,mean,sz,pz)
                print "%d\t%.3f\t%.3f"%(chrom, mean, (pz-zscoreref[chrom]['mean'])/zscoreref[chrom]['std'])
        #print total_read


















