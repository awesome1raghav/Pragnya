package com.nextron.mobile

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import com.google.gson.JsonObject
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import java.io.File
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

internal fun JsonObject?.str(key: String): String = this?.get(key)?.takeUnless { it.isJsonNull }?.asString.orEmpty()
internal fun JsonObject?.obj(key: String): JsonObject? = this?.getAsJsonObject(key)
internal fun JsonObject?.items(key: String) = this?.getAsJsonArray(key)?.mapNotNull { it.takeIf { x -> x.isJsonObject }?.asJsonObject }.orEmpty()

interface NexApi {
    @GET("health/ready") suspend fun health(): Response<JsonObject>
    @GET("cases") suspend fun cases(@Query("page_size") size: Int = 50): Response<JsonObject>
    @POST("cases") suspend fun createCase(@Body body: JsonObject): Response<JsonObject>
    @GET("cases/{id}/evidence") suspend fun evidence(@Path("id") caseId: String): Response<JsonObject>
    @Multipart @POST("cases/{id}/evidence") suspend fun upload(
        @Path("id") caseId: String, @Part file: MultipartBody.Part,
        @Part("source_type") sourceType: RequestBody,
        @Part("acquisition_method") method: RequestBody
    ): Response<JsonObject>
    @POST("evidence/{id}/analyze") suspend fun analyze(@Path("id") evidenceId: String): Response<JsonObject>
    @GET("evidence/{id}/analysis") suspend fun analysis(@Path("id") evidenceId: String): Response<JsonObject>
    @GET("jobs/{id}") suspend fun job(@Path("id") jobId: String): Response<JsonObject>
    @GET("jobs") suspend fun jobs(@Query("case_id") caseId: String? = null): Response<JsonObject>
    @GET("cases/{id}/sources") suspend fun sources(@Path("id") caseId: String): Response<JsonObject>
    @POST("cases/{id}/sources") suspend fun addSource(@Path("id") caseId: String, @Body body: JsonObject): Response<JsonObject>
    @GET("cases/{id}/reports") suspend fun reports(@Path("id") caseId: String): Response<JsonObject>
    @GET("cases/{id}/graph") suspend fun graph(@Path("id") caseId: String): Response<JsonObject>
    @GET("cases/{id}/backtracking/overview") suspend fun backtrackingOverview(@Path("id") caseId: String): Response<JsonObject>
    @GET("cases/{id}/backtracking/comparisons") suspend fun backtrackingComparisons(@Path("id") caseId: String): Response<JsonObject>
    @GET("cases/{id}/backtracking/source-occurrences") suspend fun backtrackingSources(@Path("id") caseId: String): Response<JsonObject>
    @POST("cases/{id}/backtracking/expand") suspend fun expand(@Path("id") caseId: String, @Body body: JsonObject): Response<JsonObject>
    @POST("cases/{id}/backtracking/compare") suspend fun compare(@Path("id") caseId: String, @Body body: JsonObject): Response<JsonObject>
    @POST("cases/{id}/backtracking/verify") suspend fun verify(@Path("id") caseId: String, @Body body: JsonObject): Response<JsonObject>
}

class NexRepository(private val context: Context) {
    private val prefs = context.getSharedPreferences("nextron", Context.MODE_PRIVATE)
    var baseUrl: String
        get() = prefs.getString("base_url", "").orEmpty()
        set(value) { prefs.edit().putString("base_url", value.trim().trimEnd('/') + "/").apply() }
    var caseId: String
        get() = prefs.getString("case_id", "").orEmpty()
        set(value) { prefs.edit().putString("case_id", value).apply() }

    private fun api(): NexApi {
        val address = baseUrl
        val uri = Uri.parse(address)
        require(uri.host != null && uri.path?.endsWith("/api/v1/") == true) { "Enter a backend URL ending in /api/v1/" }
        require(uri.scheme == "https" || (BuildConfig.DEBUG && uri.scheme == "http" && isLocalHost(uri.host!!))) {
            "Use HTTPS, or a private network address in debug builds"
        }
        return Retrofit.Builder().baseUrl(address).client(
            OkHttpClient.Builder().connectTimeout(8, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS)
                .callTimeout(180, TimeUnit.SECONDS).build()
        ).addConverterFactory(GsonConverterFactory.create()).build().create(NexApi::class.java)
    }

    private fun isLocalHost(host: String) = host == "10.0.2.2" || host == "127.0.0.1" || host == "localhost" ||
        host.startsWith("192.168.") || host.startsWith("10.") || host.matches(Regex("172\\.(1[6-9]|2[0-9]|3[01])\\..*"))

    private fun Response<JsonObject>.bodyOrThrow(): JsonObject {
        val body = body()
        if (!isSuccessful || body == null || body.get("success")?.asBoolean != true) {
            val error = try { com.google.gson.JsonParser.parseString(errorBody()?.string()).asJsonObject.obj("error").str("message") } catch (_: Exception) { "" }
            error(error.ifBlank { "Backend request failed: HTTP ${code()}" })
        }
        return body.getAsJsonObject("data") ?: body
    }

    // List endpoints return data arrays, so callers use the full envelope.
    private fun Response<JsonObject>.envelope(): JsonObject {
        if (!isSuccessful || body()?.get("success")?.asBoolean != true) {
            val reason = try { com.google.gson.JsonParser.parseString(errorBody()?.string()).asJsonObject.obj("error").str("message") } catch (_: Exception) { "" }
            error(reason.ifBlank { "Backend request failed: HTTP ${code()}" })
        }
        return requireNotNull(body())
    }

    suspend fun health() = api().health().bodyOrThrow()
    suspend fun cases() = api().cases().envelope().getAsJsonArray("data").map { it.asJsonObject }
    suspend fun createCase(title: String): JsonObject {
        val body = JsonObject().apply { addProperty("title", title) }
        return api().createCase(body).bodyOrThrow()
    }
    suspend fun evidence() = api().evidence(caseId).envelope().getAsJsonArray("data").map { it.asJsonObject }
    suspend fun jobs() = api().jobs(caseId.ifBlank { null }).envelope().getAsJsonArray("data").map { it.asJsonObject }
    suspend fun sources() = api().sources(caseId).envelope().getAsJsonArray("data").map { it.asJsonObject }
    suspend fun reports() = api().reports(caseId).envelope().getAsJsonArray("data").map { it.asJsonObject }
    suspend fun graph() = api().graph(caseId).bodyOrThrow()
    suspend fun backtrackingOverview() = api().backtrackingOverview(caseId).bodyOrThrow()
    suspend fun backtrackingComparisons() = api().backtrackingComparisons(caseId).bodyOrThrow()
    suspend fun backtrackingSources() = api().backtrackingSources(caseId).bodyOrThrow()
    suspend fun expand(seed: String) = api().expand(caseId, JsonObject().apply { addProperty("seed_evidence_id", seed) }).bodyOrThrow()
    suspend fun addSource(url: String) = api().addSource(caseId, JsonObject().apply { addProperty("url", url) }).bodyOrThrow()
    suspend fun analysis(evidenceId: String) = api().analysis(evidenceId).bodyOrThrow()
    suspend fun job(jobId: String) = api().job(jobId).bodyOrThrow()
    suspend fun analyze(evidenceId: String) = api().analyze(evidenceId).bodyOrThrow()
    suspend fun compare(seed: String, candidate: String) = api().compare(caseId, JsonObject().apply {
        addProperty("seed_evidence_id", seed); addProperty("candidate_evidence_id", candidate)
    }).bodyOrThrow()
    suspend fun verify(seed: String, candidate: String) = api().verify(caseId, JsonObject().apply {
        addProperty("seed_evidence_id", seed); addProperty("candidate_evidence_id", candidate)
    }).bodyOrThrow()

    suspend fun upload(uri: Uri, sourceType: String = "USER_UPLOAD", method: String = "DIRECT_UPLOAD"): JsonObject = withContext(Dispatchers.IO) {
        val resolver = context.contentResolver
        val mime = resolver.getType(uri) ?: "application/octet-stream"
        var name = "evidence"
        var length = -1L
        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                name = c.getString(0) ?: name
                if (!c.isNull(1)) length = c.getLong(1)
            }
        }
        require(length <= 500L * 1024 * 1024) { "Media exceeds the backend's 500 MB upload limit" }
        val temporary = uri.scheme != "file"
        val file = if (temporary) File.createTempFile("nextron-upload-", ".bin", context.cacheDir) else File(requireNotNull(uri.path))
        try {
            if (temporary) {
                resolver.openInputStream(uri).use { input ->
                    requireNotNull(input) { "Cannot read selected media; grant access in Android's picker" }
                    file.outputStream().use { output ->
                        val buffer = ByteArray(64 * 1024); var count = 0L
                        while (true) {
                            val n = input.read(buffer)
                            if (n < 0) break
                            count += n
                            require(count <= 500L * 1024 * 1024) { "Media exceeds the backend's 500 MB upload limit" }
                            output.write(buffer, 0, n)
                        }
                    }
                }
            } else {
                require(file.canonicalPath.startsWith(context.cacheDir.canonicalPath + File.separator)) { "Capture file is outside app cache" }
                name = file.name
            }
            val text = "text/plain".toMediaTypeOrNull()
            api().upload(caseId, MultipartBody.Part.createFormData("file", name, file.asRequestBody(mime.toMediaTypeOrNull())),
                sourceType.toRequestBody(text), method.toRequestBody(text)).bodyOrThrow()
        } finally {
            if (temporary) file.delete()
        }
    }
}
