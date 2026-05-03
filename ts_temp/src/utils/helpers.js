import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function ensureDirectory(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
  return dirPath;
}

export function generateUniqueId() {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

export function formatTimestamp(seconds) {
  const totalMs = Math.round(seconds * 1000);
  const hrs = Math.floor(totalMs / 3600000);
  const remaining = totalMs % 3600000;
  const mins = Math.floor(remaining / 60000);
  const remainingAfterMins = remaining % 60000;
  const secs = Math.floor(remainingAfterMins / 1000);
  const ms = remainingAfterMins % 1000;
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}

export function parseTimestamp(timestamp) {
  const match = timestamp.match(/(\d+):(\d+):(\d+),(\d+)/);
  if (!match) return 0;
  const [, hrs, mins, secs, ms] = match;
  return parseInt(hrs) * 3600 + parseInt(mins) * 60 + parseInt(secs) + parseInt(ms) / 1000;
}

export function getFileExtension(filename) {
  return path.extname(filename).toLowerCase();
}

export function getFileNameWithoutExtension(filename) {
  return path.basename(filename, path.extname(filename));
}

export function sanitizeFilename(filename) {
  return filename
    .replace(/[<>:"/\\|?*]/g, '_')
    .replace(/\s+/g, '_')
    .toLowerCase();
}

export function calculateVideoSegments(totalDuration, segmentDuration) {
  const segments = [];
  let currentTime = 0;
  let segmentIndex = 0;

  while (currentTime < totalDuration) {
    const endTime = Math.min(currentTime + segmentDuration, totalDuration);
    segments.push({
      index: segmentIndex,
      startTime: currentTime,
      endTime: endTime,
      duration: endTime - currentTime,
    });
    currentTime = endTime;
    segmentIndex++;
  }

  return segments;
}

export function formatDuration(seconds) {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hrs > 0) {
    return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

export async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export default {
  ensureDirectory,
  generateUniqueId,
  formatTimestamp,
  parseTimestamp,
  getFileExtension,
  getFileNameWithoutExtension,
  sanitizeFilename,
  calculateVideoSegments,
  formatDuration,
  sleep,
};