import { Uppy } from "@uppy/core";
import XHRUpload from "@uppy/xhr-upload";
import imageCompression from "browser-image-compression";

// preserveExif keeps taken_at (EXIF DateTimeOriginal) so the server can read it;
// GPS is scrubbed later, server-side, only from the *derivatives* it generates —
// see apps/uploads/tasks.py for why the original is never touched.
const RESIZE_MAX_DIMENSION = 2560;

function compressionOptionsFor(file, originalQuality) {
  if (originalQuality) return null;
  return {
    maxWidthOrHeight: RESIZE_MAX_DIMENSION,
    useWebWorker: true,
    preserveExif: true,
    fileType: file.type,
  };
}

function csrfToken() {
  return document.querySelector("meta[name=csrf-token]").content;
}

export function createUploader({ uploadUrl, maxFileMb, maxFilesBatch, onFileState, onFileRemoved }) {
  const uppy = new Uppy({
    restrictions: {
      maxFileSize: maxFileMb * 1024 * 1024,
      maxNumberOfFiles: maxFilesBatch,
      allowedFileTypes: ["image/*"],
    },
    autoProceed: false,
  }).use(XHRUpload, {
    endpoint: uploadUrl,
    fieldName: "file",
    limit: 3,
    headers: { "X-CSRFToken": csrfToken() },
    getResponseData: (text) => {
      try {
        return JSON.parse(text);
      } catch {
        return {};
      }
    },
  });

  uppy.on("file-added", (file) => onFileState(file.id, { name: file.name, state: "queued", progress: 0 }));
  uppy.on("file-removed", (file) => onFileRemoved(file.id));
  uppy.on("upload-progress", (file, p) => {
    const pct = p.bytesTotal ? Math.round((p.bytesUploaded / p.bytesTotal) * 100) : 0;
    onFileState(file.id, { state: "uploading", progress: pct });
  });
  uppy.on("upload-success", (file) => onFileState(file.id, { state: "done", progress: 100 }));
  uppy.on("upload-error", (file) => onFileState(file.id, { state: "error", progress: 0 }));

  return {
    async addFiles(fileList, originalQuality) {
      for (const file of Array.from(fileList)) {
        const opts = compressionOptionsFor(file, originalQuality);
        const data = opts ? await imageCompression(file, opts) : file;
        try {
          uppy.addFile({ name: file.name, type: file.type, data });
        } catch (err) {
          console.error("rejected file", file.name, err);
        }
      }
    },
    start() {
      return uppy.upload();
    },
    removeFile(id) {
      uppy.removeFile(id);
    },
    setCaption(id, text) {
      uppy.setFileMeta(id, { caption: text });
    },
  };
}
