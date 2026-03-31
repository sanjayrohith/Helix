import type { SliceDeploymentResult } from '../types/slice';
import { SST_NAMES } from '../types/slice';
import { ConflictAlert } from './ConflictAlert';

interface DeploymentResultProps {
  result: SliceDeploymentResult;
  onDismiss: () => void;
}

export function DeploymentResult({ result, onDismiss }: DeploymentResultProps) {
  const { success, slice_config, conflict_report, deploy_time_seconds, message } = result;

  if (!success && conflict_report.has_conflict) {
    return (
      <div className="mb-6 relative">
        <button
          onClick={onDismiss}
          className="absolute top-2 right-2 text-slate-400 hover:text-slate-200 z-10"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <ConflictAlert conflict={conflict_report} />
        <div className="mt-2 text-slate-400 text-xs">
          Processing time: {deploy_time_seconds.toFixed(2)}s
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6 bg-emerald-300/10 border border-emerald-200/30 rounded-2xl p-5 relative backdrop-blur-sm">
      <button
        onClick={onDismiss}
        className="absolute top-2 right-2 text-slate-400 hover:text-slate-200"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <div className="flex items-start gap-3 mb-4">
        <div className="flex-shrink-0">
          <svg
            className="w-6 h-6 text-success"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <div>
          <h4 className="text-emerald-200 font-semibold">Slice Deployed Successfully</h4>
          <p className="text-slate-300 text-sm">{message}</p>
        </div>
      </div>

      <div className="bg-[#081123]/90 border border-white/10 rounded-xl p-4">
        <h5 className="text-slate-100 font-medium mb-3">Generated Configuration</h5>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <ConfigRow label="Slice ID" value={slice_config.slice_id.slice(0, 8) + '...'} mono />
          <ConfigRow label="Name" value={slice_config.name} />
          <ConfigRow label="S-NSSAI SST" value={`${slice_config.sst} (${SST_NAMES[slice_config.sst]})`} mono />
          <ConfigRow label="S-NSSAI SD" value={slice_config.sd} mono />
          <ConfigRow label="5QI" value={slice_config.qos_5qi.toString()} mono />
          <ConfigRow label="ARP Priority" value={slice_config.arp_priority.toString()} mono />
          <ConfigRow label="Guaranteed BR" value={`${slice_config.guaranteed_bitrate_mbps} Mbps`} mono />
          <ConfigRow label="Max BR" value={`${slice_config.max_bitrate_mbps} Mbps`} mono />
          <ConfigRow label="Latency" value={`${slice_config.latency_ms} ms`} mono />
          <ConfigRow label="Security" value={slice_config.security_level} />
          <ConfigRow label="Isolation" value={slice_config.isolation} />
          <ConfigRow label="Device Count" value={slice_config.device_count.toLocaleString()} mono />
          <ConfigRow label="Use Case" value={slice_config.use_case} />
          <ConfigRow label="Location" value={slice_config.location} />
          <ConfigRow label="Status" value={slice_config.status} highlight />
        </div>
      </div>

      <div className="mt-3 text-slate-400 text-xs">
        Deployment time: {deploy_time_seconds.toFixed(2)}s
      </div>
    </div>
  );
}

function ConfigRow({
  label,
  value,
  mono = false,
  highlight = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  highlight?: boolean;
}) {
  return (
    <div>
      <span className="text-slate-400">{label}:</span>
      <span
        className={`ml-2 ${mono ? 'font-mono' : ''} ${
          highlight ? 'text-emerald-200 font-medium' : 'text-slate-100'
        }`}
      >
        {value}
      </span>
    </div>
  );
}
