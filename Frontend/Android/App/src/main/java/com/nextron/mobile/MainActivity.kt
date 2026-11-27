@file:Suppress("DEPRECATION")
package com.nextron.mobile

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.google.gson.JsonObject
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException

private val ink = Color(0xFF071016)
private val panel = Color(0xFF101D25)
private val accent = Color(0xFF58D5C2)
private val muted = Color(0xFF9DB0B8)

class MainActivity : ComponentActivity() {
    private var sharedUri by mutableStateOf<Uri?>(null)
    private var sharedUrl by mutableStateOf("")
    private var openedEvidence by mutableStateOf("")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        acceptShare(intent)
        setContent { NextronApp(this, sharedUri, sharedUrl, openedEvidence) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        acceptShare(intent)
    }

    private fun acceptShare(intent: Intent?) {
        openedEvidence = intent?.getStringExtra("evidence_id").orEmpty()
        if (intent?.action != Intent.ACTION_SEND) return
        sharedUri = if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                    else intent.getParcelableExtra(Intent.EXTRA_STREAM)
        sharedUrl = intent.getStringExtra(Intent.EXTRA_TEXT)?.trim().orEmpty()
    }

    fun clearSharedInput() { sharedUri = null; sharedUrl = "" }

    fun openBackend(path: String) {
        val base = NexRepository(this).baseUrl
        if (base.isNotBlank()) startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(base + path)))
    }
}

@Composable
private fun NextronApp(activity: MainActivity, shareUri: Uri?, shareUrl: String, openedEvidence: String) {
    val repo = remember { NexRepository(activity) }
    val scope = rememberCoroutineScope()
    var screen by rememberSaveable { mutableStateOf(if (repo.baseUrl.isBlank()) "SETUP" else "DASH") }
    var caseId by rememberSaveable { mutableStateOf(repo.caseId) }
    var evidenceId by rememberSaveable { mutableStateOf("") }
    var jobId by rememberSaveable { mutableStateOf("") }
    var reportId by rememberSaveable { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("") }
    var refresh by remember { mutableIntStateOf(0) }
    var cases by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var evidence by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var jobs by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var sources by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var reports by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var analysis by remember { mutableStateOf<JsonObject?>(null) }
    var comparison by remember { mutableStateOf<JsonObject?>(null) }
    var backtrackingOverview by remember { mutableStateOf<JsonObject?>(null) }
    var backtrackingComparisons by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var backtrackingSources by remember { mutableStateOf<List<JsonObject>>(emptyList()) }
    var job by remember { mutableStateOf<JsonObject?>(null) }
    var health by remember { mutableStateOf("") }

    fun execute(action: suspend () -> Unit) {
        scope.launch {
            loading = true; message = ""
            try { action() } catch (e: CancellationException) { throw e }
            catch (e: Exception) { message = e.message ?: "Request failed" }
            finally { loading = false }
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) execute {
            require(caseId.isNotBlank()) { "Select an investigation first" }
            val uploaded = repo.upload(uri)
            evidenceId = uploaded.str("evidence_id")
            jobId = uploaded.obj("analysis_job").str("job_id")
            if (jobId.isBlank()) jobId = repo.analyze(evidenceId).str("job_id")
            screen = "PROGRESS"; refresh++
        }
    }
    val overlayPermission = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        if (Settings.canDrawOverlays(activity)) {
            activity.startForegroundService(Intent(activity, BubbleService::class.java).setAction(BubbleService.START))
            message = "Floating Investigator enabled"
        } else message = "Overlay permission was not granted"
    }
    val notificationPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }

    LaunchedEffect(shareUri, shareUrl) {
        if (shareUri != null || shareUrl.isNotBlank()) screen = "UPLOAD"
    }
    LaunchedEffect(openedEvidence) {
        if (openedEvidence.isNotBlank()) { evidenceId = openedEvidence; screen = "RESULT" }
    }
    LaunchedEffect(screen, caseId, refresh) {
        if (repo.baseUrl.isBlank()) return@LaunchedEffect
        try {
            when (screen) {
                "DASH", "HISTORY" -> { health = repo.health().str("status"); cases = repo.cases(); if (caseId.isNotBlank()) jobs = repo.jobs() }
                "UPLOAD", "RESULT", "BACKTRACK" -> if (caseId.isNotBlank()) {
                    evidence = repo.evidence()
                    if (screen == "BACKTRACK") {
                        backtrackingOverview = repo.backtrackingOverview()
                        backtrackingComparisons = repo.backtrackingComparisons().items("comparisons")
                        backtrackingSources = repo.backtrackingSources().items("source_occurrences")
                    }
                }
                "SOURCES" -> if (caseId.isNotBlank()) sources = repo.sources()
                "REPORTS" -> if (caseId.isNotBlank()) reports = repo.reports()
            }
            if (screen == "RESULT" && evidenceId.isNotBlank()) analysis = repo.analysis(evidenceId)
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { message = e.message ?: "Backend unavailable" }
    }
    LaunchedEffect(screen, jobId) {
        if (screen != "PROGRESS" || jobId.isBlank()) return@LaunchedEffect
        while (screen == "PROGRESS") {
            try {
                job = repo.job(jobId)
                if (job.str("state") in listOf("COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED")) break
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { message = e.message ?: "Connection lost" }
            delay(2500)
        }
    }

    MaterialTheme(colorScheme = darkColorScheme(primary = accent, background = ink, surface = panel, onSurface = Color.White)) {
        Scaffold(containerColor = ink, bottomBar = {
            NavigationBar(containerColor = panel) {
                listOf("DASH" to "Home", "UPLOAD" to "Media", "HISTORY" to "History", "BUBBLE" to "Bubble", "SETUP" to "Connect").forEach { (route, label) ->
                    NavigationBarItem(selected = screen == route, onClick = { screen = route }, icon = { Text(label.take(1)) }, label = { Text(label) })
                }
            }
        }) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding).padding(horizontal = 18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                item { Spacer(Modifier.height(10.dp)); Text("NEXTRON", color = accent, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    Text(screenTitle(screen), color = Color.White, style = MaterialTheme.typography.titleLarge); Spacer(Modifier.height(8.dp)) }
                if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
                if (message.isNotBlank()) item { CardLine(message, Color(0xFFFFC788)) }

                when (screen) {
                    "SETUP" -> item {
                        var address by remember { mutableStateOf(repo.baseUrl) }
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Text("Enter the API address reachable from this device. Use HTTPS outside local development.", color = muted)
                            OutlinedTextField(address, { address = it }, label = { Text("Backend URL") }, placeholder = { Text("http://192.168.1.20:8000/api/v1/") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                            Button(onClick = { repo.baseUrl = address; execute { health = repo.health().str("status"); screen = "DASH" } }) { Text("Test connection") }
                            Text("Emulator: http://10.0.2.2:8000/api/v1/  ·  Phone: use your computer’s LAN address.", color = muted)
                        }
                    }
                    "DASH" -> {
                        item { CardLine("Backend: ${health.ifBlank { "checking" }}  ·  ${cases.size} investigations", accent) }
                        item {
                            var title by remember { mutableStateOf("") }
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(title, { title = it }, label = { Text("New investigation title") }, modifier = Modifier.fillMaxWidth())
                                Button(enabled = title.isNotBlank(), onClick = { execute { val created = repo.createCase(title); caseId = created.str("case_id"); repo.caseId = caseId; title = ""; refresh++ } }) { Text("Create investigation") }
                            }
                        }
                        items(cases) { c -> CardLine("${c.str("case_number")}  ${c.str("title")}", if (c.str("case_id") == caseId) accent else Color.White) {
                            caseId = c.str("case_id"); repo.caseId = caseId; screen = "UPLOAD"
                        } }
                        item { Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            SmallButton("Sources") { screen = "SOURCES" }; SmallButton("Reports") { screen = "REPORTS" }; SmallButton("Backtracking") { screen = "BACKTRACK" }
                        } }
                    }
                    "UPLOAD" -> {
                        item { CaseLabel(caseId) }
                        item { Button(enabled = caseId.isNotBlank(), onClick = { picker.launch(arrayOf("image/*", "video/*", "audio/*")) }) { Text("Choose image, video or audio") } }
                        item { OutlinedButton(enabled = caseId.isNotBlank() && Settings.canDrawOverlays(activity), onClick = {
                            activity.startForegroundService(Intent(activity, BubbleService::class.java).setAction(BubbleService.START))
                            activity.startActivity(Intent(activity, CaptureActivity::class.java).putExtra("mode", "record"))
                        }) { Text("Record screen for 15 seconds (video only)") } }
                        item { Text("Enable Floating Investigator before screen recording. Playback audio is not captured.", color = muted) }
                        if (shareUri != null) item { Button(enabled = caseId.isNotBlank(), onClick = { execute {
                            val uploaded = repo.upload(shareUri, "SHARED_FILE", "SHARE_INTENT")
                            evidenceId = uploaded.str("evidence_id"); jobId = uploaded.obj("analysis_job").str("job_id")
                            if (jobId.isBlank()) jobId = repo.analyze(evidenceId).str("job_id")
                            activity.clearSharedInput()
                            screen = "PROGRESS"
                        } }) { Text("Preserve shared media") } }
                        item {
                            var url by remember(shareUrl) { mutableStateOf(shareUrl) }
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedTextField(url, { url = it }, label = { Text("Public media or page URL") }, modifier = Modifier.fillMaxWidth())
                                Button(enabled = caseId.isNotBlank() && url.isNotBlank(), onClick = { execute { val s = repo.addSource(url); message = "Source ${s.str("state")} — retrieval queued"; screen = "SOURCES" } }) { Text("Add source to investigation") }
                            }
                        }
                        item { Text("Original bytes are uploaded. A screenshot permits image-level analysis only.", color = muted) }
                        items(evidence) { e -> CardLine("${e.str("evidence_number")}  ${e.str("filename")}  ·  ${e.str("media_type")}", Color.White) {
                            evidenceId = e.str("evidence_id"); screen = "RESULT"
                        } }
                    }
                    "PROGRESS" -> {
                        item { CardLine("Job ${job.str("job_number")}  ·  ${job.str("state").ifBlank { "loading" }}", accent) }
                        item { Text("Measured progress: ${job.obj("progress")?.toString() ?: "not reported"}", color = muted) }
                        if (job.str("state") in listOf("COMPLETED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED")) item {
                            Button(onClick = { screen = "RESULT" }) { Text("Inspect evidence and findings") }
                        }
                    }
                    "RESULT" -> {
                        item { CaseLabel(caseId); Text("Evidence $evidenceId", color = muted) }
                        item { CardLine("Latest analysis: ${analysis.obj("latest_job").str("state").ifBlank { "none" }}", accent) }
                        val findings = analysis.items("findings")
                        if (findings.isEmpty()) item { Text("No current findings. Check the job state and module limitations.", color = muted) }
                        items(findings) { f -> CardLine("${f.str("module_id")}  ${f.str("title")}\n${f.str("description")}", Color.White) }
                        items(analysis.items("modules")) { m -> CardLine("${m.str("module_id")}  ${m.str("module_name")}  ·  ${m.obj("latest").str("state").ifBlank { "not run" }}", muted) }
                        items(analysis.items("artifacts")) { a -> CardLine("Artifact: ${a.str("kind")}  ·  ${a.str("mime_type")}", accent) { activity.openBackend("artifacts/${a.str("artifact_id")}") } }
                    }
                    "SOURCES" -> {
                        item { CaseLabel(caseId); Text("Permitted public sources only. Dates and origins remain unverified until reviewed.", color = muted) }
                        if (sources.isEmpty()) item { Text("No sources recorded.", color = muted) }
                        items(sources) { s -> CardLine("${s.str("platform")}  ${s.str("title").ifBlank { s.str("url") }}\n${s.str("state")}  ·  ${s.str("claimed_publication_time").ifBlank { "Publication time unknown" }}", Color.White) }
                    }
                    "BACKTRACK" -> {
                        item { CaseLabel(caseId); Text("Bounded local expansion and preserved-media verification. External coverage is limited to permitted source records.", color = muted) }
                        item { CardLine("Compared ${backtrackingOverview.obj("coverage")?.get("compared_pairs") ?: 0} / ${backtrackingOverview.obj("coverage")?.get("possible_video_pairs") ?: 0} local video pairs", accent) }
                        val videos = evidence.filter { it.str("media_type") == "VIDEO" }
                        item {
                            var seed by remember { mutableStateOf("") }; var candidate by remember { mutableStateOf("") }
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("Choose seed", color = accent); videos.forEach { v -> SmallButton(v.str("evidence_number"), seed == v.str("evidence_id")) { seed = v.str("evidence_id") } }
                                Text("Choose candidate", color = accent); videos.forEach { v -> SmallButton(v.str("evidence_number"), candidate == v.str("evidence_id")) { candidate = v.str("evidence_id") } }
                                Button(enabled = seed.isNotBlank() && candidate.isNotBlank() && seed != candidate, onClick = { execute { comparison = repo.compare(seed, candidate) } }) { Text("Compare originals") }
                                OutlinedButton(enabled = seed.isNotBlank(), onClick = { execute {
                                    val queued = repo.expand(seed); jobId = queued.str("job_id"); evidenceId = seed; screen = "PROGRESS"
                                } }) { Text("Expand local video matches") }
                            }
                        }
                        if (comparison != null) item { CardLine("${comparison.str("status")}  ·  matched frames ${comparison?.get("matched_frames") ?: "0"}\nSubmitted coverage ${comparison?.get("submitted_coverage_percent") ?: "unavailable"}%  ·  candidate coverage ${comparison?.get("candidate_coverage_percent") ?: "unavailable"}%\nOffset ${comparison?.get("offset_s") ?: "unavailable"} s", accent) }
                        items(comparison.items("frame_pairs")) { p -> Text("Frame ${p.get("seed_t_s")} s ↔ ${p.get("candidate_t_s")} s  ·  pHash distance ${p.get("phash_distance")}", color = muted) }
                        if (backtrackingComparisons.isNotEmpty()) item { Text("Comparison history", color = accent) }
                        items(backtrackingComparisons) { c -> CardLine("${c.str("status")}  ·  ${c.str("algorithm")}\n${c.str("seed_evidence_id").take(8)} → ${c.str("candidate_evidence_id").take(8)}  ·  ${c.get("submitted_coverage_percent") ?: "?"}% / ${c.get("candidate_coverage_percent") ?: "?"}%", Color.White) }
                        if (backtrackingSources.isNotEmpty()) item { Text("Recorded source occurrences", color = accent) }
                        items(backtrackingSources) { s -> CardLine("${s.str("platform")}  ${s.str("url")}\n${s.str("outcome")}  ·  ${s.str("backtracking_access")}", muted) }
                        item { Text("Coverage measures sampled content, not manipulation confidence or proof of origin.", color = muted) }
                    }
                    "HISTORY" -> {
                        item { CaseLabel(caseId); Text("Analysis jobs from the authoritative backend", color = muted) }
                        items(jobs) { j -> CardLine("${j.str("job_number")}  ${j.str("job_type")}\n${j.str("state")}", Color.White) {
                            jobId = j.str("job_id"); evidenceId = j.str("evidence_id"); screen = "PROGRESS"
                        } }
                    }
                    "REPORTS" -> {
                        item { CaseLabel(caseId); Text("Reports require investigator review and backend generation.", color = muted) }
                        if (reports.isEmpty()) item { Text("No reports available.", color = muted) }
                        items(reports) { r -> CardLine("${r.str("report_number")}  v${r.str("version")}  ·  ${r.str("state")}", Color.White) { reportId = r.str("report_id"); screen = "REPORT_VIEW" } }
                    }
                    "REPORT_VIEW" -> {
                        val r = reports.firstOrNull { it.str("report_id") == reportId }
                        item { Text("${r.str("report_number")}  ·  ${r.str("state")}", color = accent); Text(r.obj("summary")?.toString() ?: "No summary", color = muted) }
                        if (r.str("state") == "GENERATED") item { Button(onClick = { activity.openBackend("reports/$reportId/download?format=pdf") }) { Text("Open PDF") } }
                    }
                    "BUBBLE" -> item {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            CaseLabel(caseId)
                            Text("A tap requests Android screen-capture consent. The bubble hides for capture and returns afterward.", color = muted)
                            Button(enabled = caseId.isNotBlank(), onClick = {
                                if (Build.VERSION.SDK_INT >= 33) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                                if (Settings.canDrawOverlays(activity)) activity.startForegroundService(Intent(activity, BubbleService::class.java).setAction(BubbleService.START))
                                else overlayPermission.launch(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${activity.packageName}")))
                            }) { Text("Enable Floating Investigator") }
                            OutlinedButton(onClick = { activity.startService(Intent(activity, BubbleService::class.java).setAction(BubbleService.STOP)) }) { Text("Disable bubble") }
                        }
                    }
                }
                item { Spacer(Modifier.height(24.dp)) }
            }
        }
    }
}

private fun screenTitle(screen: String) = when (screen) {
    "SETUP" -> "Backend connection"; "DASH" -> "Investigation dashboard"; "UPLOAD" -> "Acquire evidence"
    "PROGRESS" -> "Live analysis"; "RESULT" -> "Evidence findings"; "SOURCES" -> "Source records"
    "BACKTRACK" -> "Media comparison"; "HISTORY" -> "Investigation history"; "REPORTS", "REPORT_VIEW" -> "Reports"
    else -> "Floating Investigator"
}

@Composable private fun CaseLabel(id: String) { Text(if (id.isBlank()) "Select an investigation on Home" else "Active case: $id", color = muted) }

@Composable private fun CardLine(text: String, color: Color, onClick: (() -> Unit)? = null) {
    Surface(color = panel, shape = RoundedCornerShape(12.dp), onClick = onClick ?: {}) {
        Text(text, modifier = Modifier.fillMaxWidth().padding(14.dp), color = color, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable private fun SmallButton(label: String, selected: Boolean = false, onClick: () -> Unit) {
    OutlinedButton(onClick = onClick, colors = ButtonDefaults.outlinedButtonColors(contentColor = if (selected) accent else Color.White)) { Text(label) }
}
