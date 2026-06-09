import { useState } from "react";

export default function EditModal({
  content,
  onSave,
  onCancel,
}: {
  content: string;
  onSave: (s: string) => void;
  onCancel: () => void;
}) {
  const [val, setVal] = useState(content);
  return (
    <div className="overlay">
      <div className="modal">
        <div className="modal-head">
          <span>Edit proposed public content</span>
          <button className="icon-btn" onClick={onCancel}>
            ✕
          </button>
        </div>
        <textarea
          className="modal-ta"
          value={val}
          onChange={(e) => setVal(e.target.value)}
          spellCheck={false}
        />
        <div className="modal-foot">
          <button className="btn ghost" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn primary" onClick={() => onSave(val)}>
            Save &amp; Accept
          </button>
        </div>
      </div>
    </div>
  );
}
