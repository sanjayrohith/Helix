import type { ConflictReport } from '../types/slice';

interface ConflictAlertProps {
  conflict: ConflictReport;
}

export function ConflictAlert({ conflict }: ConflictAlertProps) {
  const getConflictBadgeColor = (type: string | null) => {
    const colors: Record<string, string> = {
      bandwidth: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
      snssai: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
      arp: 'bg-red-500/20 text-red-400 border-red-500/30',
      regulatory: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    };
    return colors[type || ''] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  };

  const getConflictTitle = (type: string | null) => {
    const titles: Record<string, string> = {
      bandwidth: 'Bandwidth Capacity Exceeded',
      snssai: 'S-NSSAI Collision Detected',
      arp: 'ARP Priority Conflict',
      regulatory: 'Regulatory Compliance Issue',
    };
    return titles[type || ''] || 'Conflict Detected';
  };

  return (
    <div className="bg-rose-400/10 border border-rose-300/30 rounded-2xl p-5 backdrop-blur-sm">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <svg
            className="w-6 h-6 text-danger"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h4 className="text-rose-200 font-semibold">
              {getConflictTitle(conflict.conflict_type)}
            </h4>
            <span
              className={`text-xs px-2 py-0.5 rounded border uppercase font-mono ${getConflictBadgeColor(
                conflict.conflict_type
              )}`}
            >
              {conflict.conflict_type}
            </span>
          </div>
          <p className="text-slate-200 text-sm mb-3">{conflict.details}</p>
          {conflict.suggestions.length > 0 && (
            <div>
              <h5 className="text-slate-300 text-sm font-medium mb-2">
                Recommended Actions:
              </h5>
              <ul className="list-disc list-inside text-slate-300 text-sm space-y-1">
                {conflict.suggestions.map((suggestion, index) => (
                  <li key={index}>{suggestion}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
