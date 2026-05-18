import React from "react";

const normalizeDialogText = (value) =>
  (value || "")
    .toString()
    .trim()
    .replace(/[?!.,:;]+$/g, "")
    .replace(/\s+/g, " ")
    .toLowerCase();

const ConfirmDialogIcon = ({ tone }) => {
  if (tone === "danger") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M9 3h6" />
        <path d="M10 8v7" />
        <path d="M14 8v7" />
        <path d="M5 6h14" />
        <path d="M7 6l1 13a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2l1-13" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M9.2 12.2l1.8 1.8 4-4.4" />
    </svg>
  );
};

const ConfirmDialog = ({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  tone = "default",
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;

  const shouldHideMessage = normalizeDialogText(title) === normalizeDialogText(message);
  const resolvedMessage = shouldHideMessage ? "" : message;

  return (
    <div className="modal-overlay confirm-dialog-overlay" onClick={onCancel}>
      <div className="modal-content confirm-dialog" onClick={(event) => event.stopPropagation()}>
        <div className={`confirm-dialog-badge ${tone === "danger" ? "danger" : ""}`}>
          <ConfirmDialogIcon tone={tone} />
        </div>
        <h3 className="confirm-dialog-title">{title}</h3>
        {resolvedMessage ? <p className="confirm-dialog-message">{resolvedMessage}</p> : null}
        <div className="confirm-dialog-actions">
          <button type="button" className="confirm-dialog-btn secondary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`confirm-dialog-btn ${tone === "danger" ? "danger" : "primary"}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
