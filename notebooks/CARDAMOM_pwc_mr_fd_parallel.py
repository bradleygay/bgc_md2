# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.6.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# +
import zarr
import shutil

import numpy as np
import dask.array as da

from pathlib import Path

from bgc_md2.models.CARDAMOM import CARDAMOMlib
from bgc_md2.notebookHelpers import write_to_logfile, custom_timeout

from dask.distributed import Client
# -


my_cluster = CARDAMOMlib.prepare_cluster(n_workers=48)
Client(my_cluster)

# ## How to connect to remote
# **Remark**: Port values to be adapted, see above.
#
# ### remotely
# `
# screen
# # cd GitHub/bgc_md2/notebooks/CARDAMOM
# conda activate bgc_md2
# jupyter lab --no-browser -- port=8790
# `
# ### locally
# `
# ssh -L 8080:localhost:8790 antakya_from_home
# `
#
# In browser open `localhost:8080`.
#
# To connect to bokeh dashbord
#
# `
# ssh -L 8081:localhost:8795 antakya_from_home
# `
#
# and in browser open `localhost:8081/status/`.

# +
data_folder = Path("/home/data/CARDAMOM/Greg_2020_10_26/")
output_folder = data_folder.joinpath("output")

logfilename = data_folder + filestem + output_folder + "pwc_mr_fd_notebook_dask_and_zarr.log"

#ds = xr.open_mfdataset(data_folder + filestem + "SUM*.nc")
#ds = xr.open_mfdataset(data_folder + filestem + "small_netcdf/*.nc")

zarr_path = Path(data_folder).joinpath(filestem).joinpath("zarr_version")
variable_paths = [p for p in zarr_path.iterdir() if p.is_dir()]

non_data_vars = ['lat', 'lon', 'prob', 'time']

variable_names = []
variables = []
for variable_path in variable_paths:
    name = variable_path.name
    if name not in non_data_vars:
        variable_names.append(name)
        variables.append(da.from_zarr(str(variable_path)))
        
variables.append(da.from_zarr(str(zarr_path.joinpath('lat')), chunks=(1,)).reshape(-1, 1, 1, 1))
variable_names.append('lat')
variables.append(da.from_zarr(str(zarr_path.joinpath('lon')), chunks=(1,)).reshape(1, -1, 1, 1))
variable_names.append('lon')
variables.append(da.from_zarr(str(zarr_path.joinpath('prob')), chunks=(1,)).reshape(1, 1, -1, 1))
variable_names.append('prob')
variables.append(da.from_zarr(str(zarr_path.joinpath('time'))).reshape(1, 1, 1, -1))
variable_names.append('time')

variables


# +
lims = (None, None, 2)

for nr, name, var in zip(range(len(variables)), variable_names, variables):
    if name not in non_data_vars:
#        variables[nr] = variables[nr][:nr_lim, :nr_lim, :nr_lim, ...]
        variables[nr] = variables[nr][:lims[0], :lims[1], :lims[2], ...]
  
name = "lat"
index = variable_names.index(name)
variables[index] = variables[index][:lims[0], ...]

name = "lon"
index = variable_names.index(name)
variables[index] = variables[index][:, :lims[1], ...]

name = "prob"
index = variable_names.index(name)
variables[index] = variables[index][:, :, 0:(0+lims[2]), ...]

#for nr, name in enumerate(['lat', 'lon', 'prob']):
#    index = variable_names.index(name)
#    idx = [slice(None)] * nr + [slice(0, lims[nr], 1)]
#    print(idx)
#    variables[index] = variables[index][idx]

nr_times = variables[variable_names.index('time')].shape[-1]
nr_pools = 6

variables
# -

for name in ["lat", "lon", "prob"]:#, "time"]:
    val = variables[variable_names.index(name)]
    val.to_zarr(data_folder + filestem + output_folder + name)


# +
#from time import sleep

def func_start_values(*args):
    v_names = args[-1]
    d = {v_names[i]: args[i].reshape((-1,)) for i in range(len(args[:-1]))}
#    print([v.shape for v in d.values()])
    print('lat:', d['lat'], 'lon:', d['lon'], 'prob:', d['prob'], flush=True)
#    print('time:', d['time'], flush=True)
#    print([v.shape for v in d.values()], flush=True)

    start_values = CARDAMOMlib.load_start_values_greg_dict(d)
#    print(start_values, flush=True)

#    start_values = da.from_array(1.1 * np.ones((1, 1, 1, 6), dtype=np.float64, chunks=(1,1,6))
#    start_values.to_dask()
    return start_values.reshape(1, 1, 1, nr_pools)


# +
#shape = (34, 71, 50, 6)                                                                                         
#chunks = (1, 1, 1, 6)                   
#
## set up zarr array to store data
#store = zarr.DirectoryStore('TB1.zarr')
#root = zarr.group(store) 
#TB1 = root.zeros(
#    'data', 
#    shape=shape, 
#    chunks=chunks, 
#    dtype=np.float64
#)
# -

start_values = variables[0].map_blocks(
    func_start_values,
    *variables[1:],
    variable_names,
    drop_axis=3,
    new_axis=3,
    chunks=(1, 1, 1, 6),
    dtype=np.float64,
    meta=np.ndarray((34, 71, 50, 6), dtype=np.float64)
)
start_values

# +
# %%time

#start_values.compute()
start_values_delayed = start_values.to_zarr(
    data_folder + filestem + output_folder + "start_values",
    overwrite=True,
    lock=False,
    return_stored=False,
    compute=False,
    kwargs={'chunks': (1, 1, 1, nr_pools)}
)
#start_values_delayed = start_values.store(TB1, lock=False, compute=False)   

# +
#start_values_delayed.visualize(optimize_graph=True)

# +
# %%time

#_ = da.compute(start_values_delayed, scheduler="distributed")
start_values_delayed.compute()


# -
def func_us(*args):
    v_names = args[-1]
    d = {v_names[i]: args[i].reshape((-1,)) for i in range(len(args[:-1]))}
#    print([v.shape for v in d.values()])
    print('lat:', d['lat'], 'lon:', d['lon'], 'prob:', d['prob'], flush=True)
#    print('time:', d['time'], flush=True)
#    print([v.shape for v in d.values()], flush=True)

    us = CARDAMOMlib.load_us_greg_dict(d)
#    print(start_values, flush=True)

    return us.reshape(1, 1, 1, nr_times, nr_pools)


us = variables[0].map_blocks(
    func_us,
    *variables[1:],
    variable_names,
    new_axis=4,
    chunks=(1, 1, 1, nr_times, nr_pools),
    dtype=np.float64,
    meta=np.ndarray((1, 1, 1, nr_times, nr_pools), dtype=np.float64)
)
us

# +
# %%time

us.to_zarr(data_folder + filestem + output_folder + "us")


# -

def func_Bs(*args):
    v_names = args[-3]
    time_limit_in_min = args[-2]
    return_shape = args[-1]
    d = {v_names[i]: args[i].reshape((-1,)) for i in range(len(args[:-3]))}
#    print([v.shape for v in d.values()])
#    print('lat:', d['lat'], 'lon:', d['lon'], 'prob:', d['prob'], flush=True)
#    print('time:', d['time'], flush=True)
#    print([v.shape for v in d.values()], flush=True)

    Bs = -np.inf * np.ones(return_shape)
    start_time = time.time()
    timeout_msg = ""
    try:
        Bs = custom_timeout(
            time_limit_in_min*60,
            CARDAMOMlib.load_Bs_greg_dict,
            d,
#            integration_method="trapezoidal",
#            nr_nodes=11
        )
    except TimeoutError:
        duration = (time.time() - start_time) / 60
        timeout_msg = 'Timeout after %2.2f minutes' % duration
        print(timeout_msg)

    write_to_logfile(
           logfilename,
        "finished single,",
        "lat:", d["lat"],
        "lon:", d["lon"],
        "prob:", d["prob"],
        timeout_msg
    )

    return Bs.reshape(return_shape)


# +
return_shape = (1, 1, 1, nr_times, nr_pools, nr_pools)

Bs = variables[0].map_blocks(
    func_Bs,
    *variables[1:],
    variable_names,
    20, # time_limit_in_min
    return_shape,
    new_axis=[4, 5],
    chunks=return_shape,
    dtype=np.float64,
    meta=np.ndarray(return_shape, dtype=np.float64)
)
Bs


# +
# #%%time
#
## replace by Markus version and compute and save batchwise
#Bs.to_zarr(data_folder + filestem + output_folder + "Bs", overwrite=True)
#write_to_logfile(logfilename, 'done')
#print('done')

# +
def batchwise_to_zarr_CARDAMOM(arr: dask.array.core.Array, zarr_dir_name: str, rm=False):
    dir_p = Path(zarr_dir_name)
    if rm & dir_p.exists():
        shutil.rmtree(dir_p)

#    if arr.nbytes < 8 * 1024 ** 3:
    if False:
        # if the array fits into memory
        # the direct call of the to_zarr method
        # is possible (allthough it seems to imply a compute()
        # for the whole array or at least a part that is too big
        # to handle for bigger arrays
        arr.to_zarr(zarr_dir_name)
    else:
        # if the array is bigger than memory we compute explicitly
        # a part of it and write it to the zarr array.
        # This takes longer but gives us control over the
        # memory usage
        z = zarr.open(zarr_dir_name, mode="w", shape=arr.shape, chunks=arr.chunksize)
        slices_lat = np.array_split(range(arr.shape[1]), 10)
        slices_prob = np.array_split(range(arr.shape[2]), 1)
        
        slices_tuples = [(l, p) for l in slices_lat for p in slices_prob]
        for s in slices_tuples:
            print(s)
            l = slice(s[0][0], s[0][-1]+1, 1)
            p = slice(s[1][0], s[1][-1]+1, 1)
            z[:, l, p, ...] = arr[:, l, p, ...].compute()


# -

# write header to logfile
c = Bs.chunks
nr_chunks = np.prod([len(val) for val in c])
print('nr_chunks:', nr_chunks)
nr_singles = np.prod(Bs.shape[:3])
print('nr_singles:', nr_singles)
write_to_logfile(
    logfilename,
    'starting:',
#    nr_chunks, "chunks, ",
    nr_singles, "singles"
)

# +
# %%time

batchwise_to_zarr_CARDAMOM(Bs, data_folder + filestem + output_folder + "Bs", rm=True)
write_to_logfile(logfilename, 'done')
print('done')
# -



Bs_zarr = zarr.open(data_folder + filestem + output_folder + "Bs")
da_Bs_restricted = da.from_zarr(Bs_zarr)[:, :, :, 0, 0, 0]
da_Bs_restricted

# +
timeout_coords = np.where(da_Bs_restricted.compute()==-np.inf)
timeout_nrs = len(timeout_coords[0])

timeout_coords

# +
timeout_variables = []
for v, name in zip(variables, variable_names):
    if name not in non_data_vars:
        v_stack_list = []
        for lat, lon, prob in zip(*[timeout_coords[k] for k in range(3)]):
            v_stack_list.append(v[lat, lon, prob])
            
        timeout_variables.append(da.stack(v_stack_list))

timeout_variables.append(da.from_array(timeout_coords[0].reshape(-1, 1), chunks=(1, 1))) # lat
timeout_variables.append(da.from_array(timeout_coords[1].reshape(-1, 1), chunks=(1, 1))) # lon
timeout_variables.append(da.from_array(timeout_coords[2].reshape(-1, 1), chunks=(1, 1))) # prob

timeout_variables.append(variables[variable_names.index('time')].reshape(1, -1))
timeout_variables

# +
return_shape = (1, nr_times, nr_pools, nr_pools)

timeout_Bs = timeout_variables[0].map_blocks(
    func_Bs,
    *timeout_variables[1:],
    variable_names,
    2000, # time_limit_in_min
    return_shape,
    new_axis=[2, 3],
    chunks=return_shape,
    dtype=np.float64,
    meta=np.ndarray(return_shape, dtype=np.float64)
)
timeout_Bs
# -

# write header to logfile
c = timeout_Bs.chunks
nr_chunks = np.prod([len(val) for val in c])
print('nr_chunks:', nr_chunks)
nr_singles = timeout_Bs.shape[0]
print('nr_singles:', nr_singles)
write_to_logfile(
    logfilename,
    'starting:',
#    nr_chunks, "chunks, ",
    nr_singles, "timeout singles"
)

# +
# %%time

timeout_Bs_computed = timeout_Bs.compute()
write_to_logfile(logfilename, 'done')

timeout_nrs = len(timeout_coords[0])
for nr, lat, lon, prob in zip(range(timeout_nrs), *[timeout_coords[k] for k in range(3)]):
    Bs_zarr[lat, lon, prob, ...] = timeout_Bs_computed[nr, ...]
# -



da_Bs_done_restricted = da.from_zarr(Bs_zarr)[:, :, :, 0, 0, 0]
timeout_coords = np.where(da_Bs_done_restricted.compute()==-np.inf)
timeout_coords

len(timeout_coords[0])







def func_xs(*args):
    v_names = args[-1]
    d = {v_names[i]: args[i].reshape((-1,)) for i in range(len(args[:-1]))}
    xs = CARDAMOMlib.load_xs_greg_dict(d)

    return xs.reshape(1, 1, 1, nr_times, nr_pools)


xs = variables[0].map_blocks(
    func_xs,
    *variables[1:],
    variable_names,
    new_axis=4,
    chunks=(1, 1, 1, nr_times, nr_pools),
    dtype=np.float64,
    meta=np.ndarray((1, 1, 1, nr_times, nr_pools), dtype=np.float64)
)
xs

# +
# %%time

xs.to_zarr(data_folder + filestem + output_folder + "xs")
# -



def func_Us(*args):
    v_names = args[-1]
    d = {v_names[i]: args[i].reshape((-1,)) for i in range(len(args[:-1]))}
    Us = CARDAMOMlib.load_Us_greg_dict(d)

    return Us.reshape(1, 1, 1, nr_times, nr_pools)


Us = variables[0].map_blocks(
    func_Us,
    *variables[1:],
    variable_names,
    new_axis=4,
    chunks=(1, 1, 1, nr_times, nr_pools),
    dtype=np.float64,
    meta=np.ndarray((1, 1, 1, nr_times, nr_pools), dtype=np.float64)
)
Us

# +
# %%time

Us.to_zarr(data_folder + filestem + output_folder + "Us")
# -



def func_Fs(*args):
    v_names = args[-1]
    d = {v_names[i]: args[i].reshape((-1,)) for i in range(len(args[:-1]))}
    Fs = CARDAMOMlib.load_Fs_greg_dict(d)

    return Fs.reshape(1, 1, 1, nr_times, nr_pools, nr_pools)


Fs = variables[0].map_blocks(
    func_Fs,
    *variables[1:],
    variable_names,
    new_axis=(4, 5),
    chunks=(1, 1, 1, nr_times, nr_pools, nr_pools),
    dtype=np.float64,
    meta=np.ndarray((1, 1, 1, nr_times, nr_pools, nr_pools), dtype=np.float64)
)
Fs

# +
# %%time

Fs.to_zarr(data_folder + filestem + output_folder + "Fs")
# -



def func_Rs(*args):
    v_names = args[-1]
    d = {v_names[i]: args[i].reshape((-1,)) for i in range(len(args[:-1]))}
    Rs = CARDAMOMlib.load_Rs_greg_dict(d)

    return Rs.reshape(1, 1, 1, nr_times, nr_pools)


Rs = variables[0].map_blocks(
    func_Rs,
    *variables[1:],
    variable_names,
    new_axis=4,
    chunks=(1, 1, 1, nr_times, nr_pools),
    dtype=np.float64,
    meta=np.ndarray((1, 1, 1, nr_times, nr_pools), dtype=np.float64)
)
Rs

# +
# %%time

Rs.to_zarr(data_folder + filestem + output_folder + "Rs")
# -


