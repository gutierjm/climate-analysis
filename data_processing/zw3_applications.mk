# zw3_applications.mk
#
# To execute:
#   make -n -B -f zw3_applications.mk  (-n is a dry run) (-B is a force make)

## Define marcos ##
include zw3_climatology_config.mk
include zw3_climatology.mk

## Phony target
all : ${TARGET}

### Plot the envelope ###

## Step 1: Calculate the contour zonal anomaly ##
CONTOUR_ORIG=${DATA_DIR}/${CONTOUR_VAR}_${DATASET}_${LEVEL}_daily_native.nc
CONTOUR_ZONAL_ANOM=${DATA_DIR}/${CONTOUR_VAR}_${DATASET}_${LEVEL}_daily_native-zonal-anom.nc       
${CONTOUR_ZONAL_ANOM} : ${CONTOUR_ORIG}
	${ZONAL_ANOM_METHOD} $< ${CONTOUR_VAR} $@
	ncatted -O -a axis,time,c,c,T $@

## Step 2: Apply temporal averaging to the zonal contour data ##
CONTOUR_ZONAL_ANOM_RUNMEAN=${DATA_DIR}/${CONTOUR_VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_native-zonal-anom.nc 
${CONTOUR_ZONAL_ANOM_RUNMEAN} : ${CONTOUR_ZONAL_ANOM}
	cdo ${TSCALE} $< $@
	ncatted -O -a axis,time,c,c,T $@

## Step 3: Plot the envelope for a selection of individual timesteps ##
ENV_PLOT=${MAP_DIR}/env/${TSCALE_LABEL}/${VAR}/env-${ENV_WAVE_LABEL}-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}_${PLOT_END}.png 
${ENV_PLOT}: ${ENV_3D} ${CONTOUR_ZONAL_ANOM_RUNMEAN}
	${CDAT} ${VIS_SCRIPT_DIR}/plot_envelope.py $< ${VAR} ${TSTEP} --contour $(word 2,$^) ${CONTOUR_VAR} --timescale ${TSCALE_LABEL} --time ${PLOT_START} ${PLOT_END} none --projection spstere --stride ${STRIDE} --raphael --ofile $@

## Step 4: Plot the climatological mean envelope ##

ENV_CLIM=${ZW3_DIR}/env_zw3_${ENV_WAVE_LABEL}_${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}-clim_${GRID}.nc
${ENV_CLIM} : ${ENV_3D} 
	${PYTHON} ${DATA_SCRIPT_DIR}/calc_composite.py $< ${VAR} $@

ENV_CLIM_PLOT=${MAP_DIR}/env_zw3_${ENV_WAVE_LABEL}_${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}-clim_${GRID}.png
${ENV_CLIM_PLOT} : ${ENV_CLIM}
	${CDAT} ${VIS_SCRIPT_DIR}/plot_composite.py $< ${VAR}_annual ${VAR}_DJF ${VAR}_MAM ${VAR}_JJA ${VAR}_SON --headings annual DJF MAM JJA SON --units ms-1 --palette hot_r --ticks 0 1 2 3 4 5 6 7 8 --extend max --projection spstere --ofile $@



### Plot the Hilbert transform ###

HILBERT_PLOT=${INDEX_DIR}/hilbert/${TSCALE_LABEL}/hilbert_zw3_${ENV_WAVE_LABEL}_${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}-${LAT_LABEL}_${PLOT_END}.png 
${HILBERT_PLOT}: ${V_RUNMEAN}
	${CDAT} ${VIS_SCRIPT_DIR}/plot_hilbert.py $< ${VAR} ${TSTEP} $@ --timescale ${TSCALE_LABEL} --time ${PLOT_START} ${PLOT_END} none --latitude ${LAT_RANGE} --stride ${STRIDE}


### Index comparisons ###

## Plot 1: My metric versus wave 3 ##

METRIC_VS_WAVE3_PLOT=${INDEX_DIR}/${METRIC}-vs-wave3_zw3_${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}-${MER_METHOD}.png
${METRIC_VS_WAVE3_PLOT} : ${WAVE_STATS} ${FOURIER_INFO}
	${PYTHON} ${VIS_SCRIPT_DIR}/plot_scatter.py $(word 1,$^) ${METRIC} $(word 2,$^) wave3_amp $@ --colour $(word 2,$^) wave4_amp --normalise --trend_line --thin 3 --cmap hot_r --ylabel wave_3 --xlabel my_index --ylat ${LAT_SEARCH_MIN} ${LAT_SEARCH_MAX} ${MER_METHOD} --clat ${LAT_SEARCH_MIN} ${LAT_SEARCH_MAX} ${MER_METHOD}

## Plot 2: My metric versus ZW3 index ##

METRIC_VS_ZW3_PLOT=${INDEX_DIR}/${METRIC}-vs-zw3index_zw3_${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}-${MER_METHOD}.png
${METRIC_VS_ZW3_PLOT} : ${WAVE_STATS} ${ZW3_INDEX} ${FOURIER_INFO}
	${PYTHON} ${VIS_SCRIPT_DIR}/plot_scatter.py $(word 1,$^) ${METRIC} $(word 2,$^) zw3 $@ --colour $(word 3,$^) wave3_phase --normalise --trend_line --thin 3 --cmap jet --ylabel ZW3_index --xlabel my_index --clat ${LAT_SINGLE} ${LAT_SINGLE} none

## Plot 3: My metric versus SAM and ENSO ##

##FIXME


### Climatological stats ###

## Plot 1: Monthly totals histogram ##

MONTHLY_TOTALS_PLOT=${INDEX_DIR}/clim/montots_zw3_${METRIC}${METRIC_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}-${MER_METHOD}.png 
${MONTHLY_TOTALS_PLOT} : ${WAVE_STATS} 
	${PYTHON} ${DATA_SCRIPT_DIR}/parse_wave_stats.py $< ${METRIC} --monthly_totals_histogram $@ --metric_filter ${METRIC_THRESH}

## Plot 2: Seasonal values line graph ##

SEASONAL_VALUES_PLOT=${INDEX_DIR}/clim/seasvals_zw3_${METRIC}${METRIC_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}-${MER_METHOD}.png 
${SEASONAL_VALUES_PLOT}: ${WAVE_STATS} 
	${PYTHON} ${DATA_SCRIPT_DIR}/parse_wave_stats.py $< ${METRIC} --seasonal_values_line $@ --metric_filter ${METRIC_THRESH}


### Calculate composite envelope (with zg overlay) ###

## Step 1: Get the composite mean envelope ##

COMP_ENV_FILE=${COMP_DIR}/env-composite_zw3_${METRIC}${METRIC_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}.nc 
${COMP_ENV_FILE} : ${ENV_3D} ${DATE_LIST} 
	${PYTHON} ${DATA_SCRIPT_DIR}/calc_composite.py $< ${VAR} $@ --date_file $(word 2,$^) 

## Step 2: Get the composite mean contour ##

CONTOUR_ZONAL_ANOM_RUNMEAN_COMP=${COMP_DIR}/${CONTOUR_VAR}-composite_zw3_${METRIC}${METRIC_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}-${CONTOUR_VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_native-zonal-anom.nc 
${CONTOUR_ZONAL_ANOM_RUNMEAN_COMP} : ${CONTOUR_ZONAL_ANOM_RUNMEAN} ${DATE_LIST} 
	${PYTHON} ${DATA_SCRIPT_DIR}/calc_composite.py $< ${CONTOUR_VAR} $@ --date_file $(word 2,$^)

## Step 3: Plot ##

COMP_ENV_PLOT=${COMP_DIR}/env-composite_zw3_${METRIC}${METRIC_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}-zg_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}-zonal-anom.png
${COMP_ENV_PLOT} : ${COMP_ENV_FILE} ${CONTOUR_ZONAL_ANOM_RUNMEAN_COMP}
	${CDAT} ${DATA_SCRIPT_DIR}/plot_composite.py $(word 1,$^)  ${VAR}_annual ${VAR}_DJF ${VAR}_MAM ${VAR}_JJA ${VAR}_SON --headings annual DJF MAM JJA SON --ticks 0 1 2 3 4 5 6 7 8 9 10 --units ms-1 --projection spstere --palette hot_r --countour_file $(word 2,$^) --contour_vars ${CONTOUR_VAR}_annual ${CONTOUR_VAR}_DJF ${CONTOUR_VAR}_MAM ${CONTOUR_VAR}_JJA ${CONTOUR_VAR}_SON  --ofile $@


### Calculate composite for variable of interest (e.g. tas, pr, sic) two ways ###

## Step 1: Generate list of dates for use in composite creation ##

DATE_LIST=${COMP_DIR}/dates_zw3_${METRIC}${METRIC_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}_${GRID}-${MER_METHOD}.txt 
${DATE_LIST}: ${WAVE_STATS}
	${PYTHON} ${DATA_SCRIPT_DIR}/parse_wave_stats.py $< ${METRIC} --date_list $@ --metric_filter ${METRIC_THRESH}

## Step 2: Calculate the anomaly for the variable of interest and apply temporal averaging ##

COMP_VAR_ORIG=${DATA_DIR}/${COMP_VAR}_${DATASET}_surface_daily_${GRID}.nc
COMP_VAR_ANOM_RUNMEAN=${DATA_DIR}/${COMP_VAR}_${DATASET}_surface_${TSCALE_LABEL}-anom-wrt-all_native.nc
${COMP_VAR_ANOM_RUNMEAN} : ${COMP_VAR_ORIG} 
	cdo ${TSCALE} -ydaysub $< -ydayavg $< $@
	ncatted -O -a axis,time,c,c,T $@

## Step 3a: Calculate composite - way 1 ##

COMP_VAR_FILE=${COMP_DIR}/${COMP_VAR}-composite_zw3_${METRIC}${METRIC_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}-anom-wrt-all_${GRID}.nc 
${COMP_VAR_FILE} : ${COMP_VAR_ANOM_RUNMEAN} ${DATE_LIST} 
	${PYTHON} ${DATA_SCRIPT_DIR}/calc_composite.py $< ${COMP_VAR} $@ --date_file $(word 2,$^) 

## Step 3b: Plot composite - way 1 ##

COMP_VAR_PLOT=${COMP_DIR}/${COMP_VAR}-composite_zw3_${METRIC}${METRIC_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}-anom-wrt-all_${GRID}.png
${COMP_VAR_PLOT} : ${COMP_VAR_FILE}
	${CDAT} ${DATA_SCRIPT_DIR}/plot_composite.py $< ${COMP_VAR}_annual ${COMP_VAR}_DJF ${COMP_VAR}_MAM ${COMP_VAR}_JJA ${COMP_VAR}_SON --headings annual DJF MAM JJA SON --ticks -3.0 -2.5 -2.0 -1.5 -1.0 -0.5 0 0.5 1.0 1.5 2.0 2.5 3.0 --units temperature_anomaly --projection spstere --ofile $@


## Step 4: Calculate composite - way 2 ##

COMP_METRIC_FILE=${COMP_DIR}/${METRIC}-composite_zw3_${COMP_VAR}${COMP_THRESH}-${ENV_WAVE_LABEL}_env-${VAR}_${DATASET}_${LEVEL}_${TSCALE_LABEL}-anom-wrt-all_${GRID}.nc
${COMP_METRIC_FILE} : ${COMP_VAR_ANOM_RUNMEAN} ${WAVE_STATS}
	${PYTHON} ${DATA_SCRIPT_DIR}/calc_index_composite.py $(word 1,$^) ${COMP_VAR} $(word 2,$^) ${METRIC} ${COMP_THRESH} $@



#
## Optional extras ##
#
# plot_composite.py   --   plot a composite
