#!/bin/bash
# Convert report.docx to report.pdf with Microsoft Word (macOS). Run from anywhere.
P="$(cd "$(dirname "$0")" && pwd)"
osascript <<EOS
tell application "Microsoft Word"
  open POSIX file "$P/report.docx"
  delay 4
  set d to active document
  save as d file name "$P/report.pdf" file format format PDF
  close d saving no
end tell
EOS
