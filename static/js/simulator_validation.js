(function (root) {
  'use strict';
  function simulatorEntryErrors(values) {
    if (!values.simulator) return {};
    if (!['FFS', 'FTD', 'ATD'].includes(values.device_type)) return {device_type: 'Select device type.'};
    if (values.device_type === 'ATD' && !['BATD', 'AATD'].includes(values.atd_type)) return {atd_type: 'Select BATD or AATD.'};
    if (!String(values.device_id || '').trim()) return {device_id: 'Device ID required.'};
    if (values.instrument_credit_eligible && !values.dual) return {dual: 'Dual required.'};
    const duration = Number(values.duration || 0);
    const instrument = Number(values.simulated_instrument || 0);
    if (!(duration > 0)) return values.instrument_credit_eligible ? {duration: 'Duration required.'} : {};
    if (instrument > duration) return {simulated_instrument: 'Cannot exceed duration.'};
    if (values.instrument_credit_eligible && !(instrument > 0)) return {simulated_instrument: 'Instrument time required.'};
    return {};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {simulatorEntryErrors};
  else root.simulatorEntryErrors = simulatorEntryErrors;
}(typeof window === 'undefined' ? this : window));
