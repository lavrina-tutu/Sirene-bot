package org.mpxj.mpp;

import java.util.*;
import org.mpxj.ProjectFile;
import org.mpxj.common.ByteArrayHelper;

/** Observation only; no relation mutation and no second read/parser. */
public final class RelationReadAudit {
    private static final Map<ProjectFile, Map<String,Object>> AUDITS = Collections.synchronizedMap(new WeakHashMap<>());
    public static void begin(ProjectFile file, int count) {
        Map<String,Object> audit = new LinkedHashMap<>();
        audit.put("expected_count", count); audit.put("complete", false);
        audit.put("records", new ArrayList<Map<String,Object>>()); AUDITS.put(file, audit);
    }
    @SuppressWarnings("unchecked")
    static void record(ProjectFile file, int position, String disposition, byte[] data) {
        Map<String,Object> row = new LinkedHashMap<>();
        row.put("position", position); row.put("disposition", disposition);
        if (data != null) {
            row.put("raw_hex", hex(data));
            if (data.length >= 14) {
                row.put("uid", ByteArrayHelper.getInt(data, 0));
                row.put("predecessor_uid", ByteArrayHelper.getInt(data, 4));
                row.put("successor_uid", ByteArrayHelper.getInt(data, 8));
                row.put("type_code", (int)ByteArrayHelper.getShort(data, 12));
            }
        }
        ((List<Map<String,Object>>)AUDITS.get(file).get("records")).add(row);
    }
    public static void finish(ProjectFile file) { AUDITS.get(file).put("complete", true); }
    public static Map<String,Object> get(ProjectFile file) { return AUDITS.get(file); }
    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder();
        for (byte b: bytes) result.append(String.format("%02x", b & 255));
        return result.toString();
    }
}
