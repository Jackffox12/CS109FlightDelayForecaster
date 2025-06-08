import { motion, AnimatePresence } from 'framer-motion';
import type { PanInfo } from 'framer-motion';
import dayjs from 'dayjs';

type Data = {
  origin: string; 
  dest: string; 
  p_late: number;
  sched_dep_local: string | null; 
  pred_dep_local: string | null;
  alpha: number; 
  beta: number; 
  updated: boolean;
};

type Props = { 
  isOpen: boolean; 
  onClose: () => void; 
  data: Data 
};

export function BottomSheet({ isOpen, onClose, data }: Props) {
  const sheetVariants = { 
    open: { y: 0 }, 
    closed: { y: '100%' } 
  };

  const handleDragEnd = (_: any, info: PanInfo) => {
    if (info.offset.y > 120) onClose();   // swipe-down closes
  };

  return (
    <>
      {/* Backdrop overlay - tap to close */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="backdrop"
            className="fixed inset-0 z-30 bg-black/20"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
        )}
      </AnimatePresence>

      {/* Bottom sheet */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="sheet"
            className="fixed inset-x-0 bottom-0 z-50 w-full
                       h-[40vh] md:h-[30vh] bg-white/15 backdrop-blur-lg
                       rounded-t-2xl px-6 py-4 text-white touch-none"
            initial="closed"
            animate="open"
            exit="closed"
            variants={sheetVariants}
            transition={{ type: 'spring', stiffness: 260, damping: 32 }}
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            onDragEnd={handleDragEnd}
          >
            {/* handle bar */}
            <div className="w-10 h-1.5 bg-gray-300/80 rounded-full mx-auto mb-3" />

            <div className="flex flex-col md:flex-row md:items-center md:justify-between h-full">
              {/* big % */}
              <div className="text-center md:text-left space-y-1">
                <p className="text-5xl font-bold">{(data.p_late * 100).toFixed(1)}%</p>
                <p className="text-xs">chance of departing ≥15 min late</p>
              </div>

              {/* detail grid */}
              <div className="mt-4 md:mt-0 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-sm">
                <span className="text-gray-300">Route</span>
                <span>{data.origin} ▸ {data.dest}</span>

                <span className="text-gray-300">Scheduled</span>
                <span>{data.sched_dep_local ? dayjs(data.sched_dep_local).format('LT') : '—'}</span>

                <span className="text-gray-300">Predicted</span>
                <span>{data.pred_dep_local ? dayjs(data.pred_dep_local).format('LT') : '—'}</span>

                <span className="text-gray-300">α / β</span>
                <span>{data.alpha.toFixed(2)} / {data.beta.toFixed(2)}</span>

                <span className="text-gray-300">Updated</span>
                <span>{String(data.updated)}</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
} 