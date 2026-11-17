# MPXJ 16.4.0: relation read observation overlay

The pinned stock JAR is unchanged. read_mpp starts JVM with this overlay first.
ConstraintFactory remains the single binary parser; each metadata row emits one
observation with position, disposition and original bytes. Deleted rows are
observed separately. Self, project-summary, dangling and malformed records are
never silently called represented. Completion is emitted only after the loop.
Unsupported formats or an already-started unpatched JVM have no audit: fail closed.

Rebuild: PYTHONPATH=/home/tkachenkoav/.local/lib/python3.9/site-packages
/usr/bin/python3.9 references/mpxj-16.4.0-observation/build.py
(run from MppReader, combine the two lines as environment and command).
ECJ is pinned for the JRE-only host. Sources/compiler are vendored, hashes checked;
ZIP entries use fixed timestamps. All input/output hashes are in manifest.json.
MPXJ licensing: LGPL-2.1, see the upstream source archive META-INF and project LICENSE.
No second parser, service or product CLI is introduced by this build recipe.

getWorkSplits returns working ranges, not interruptions. A single continuous
range is not a split defect. Raw periods are kept unchanged for normalization.
Timephased source planned, actual regular/overtime and remaining regular/overtime
are separate. getTimephasedWork(List<LocalDateTimeRange>,TimeUnit.HOURS) projects
actual+remaining over explicit source boundaries; it never replaces raw planned.
