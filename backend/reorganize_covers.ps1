# 封面文件整理脚本
# 将 data/covers/{code}-{type}.jpg 移动到 data/covers/{code}/{code}-{type}.jpg

$ErrorActionPreference = "Stop"
$coversDir = "F:\github\MyMovieDB\data\covers"
$dbPath = "F:\github\MyMovieDB\data\movies.db"

Write-Host "=" * 60
Write-Host "封面文件整理工具"
Write-Host "=" * 60

# 获取所有封面文件
$files = Get-ChildItem -Path $coversDir -Filter "*.jpg" -File
Write-Host "`n📁 扫描到 $($files.Count) 个文件"

# 按番号分组
$codes = @{}
foreach ($file in $files) {
    $name = $file.BaseName
    
    # 提取番号 (去掉 -poster, -fanart, -thumb 后缀)
    $code = $name -replace '-poster$', '' -replace '-fanart$', '' -replace '-thumb$', ''
    
    if (-not $codes.ContainsKey($code)) {
        $codes[$code] = @()
    }
    $codes[$code] += $file
}

Write-Host "📋 发现 $($codes.Count) 个番号: $($codes.Keys -join ', ')"

# 整理每个番号
$movedCount = 0
$nfoCount = 0

foreach ($code in $codes.Keys | Sort-Object) {
    Write-Host "`n$('='*50)"
    Write-Host "处理: $code"
    
    # 创建番号文件夹
    $codeDir = Join-Path $coversDir $code
    if (-not (Test-Path $codeDir)) {
        New-Item -ItemType Directory -Path $codeDir -Force | Out-Null
        Write-Host "📁 创建文件夹: $codeDir"
    }
    
    # 移动文件
    foreach ($file in $codes[$code]) {
        $newPath = Join-Path $codeDir $file.Name
        Move-Item -Path $file.FullName -Destination $newPath -Force
        Write-Host "  ✅ 移动: $($file.Name) -> $code/$($file.Name)"
        $movedCount++
    }
    
    # 生成 NFO 文件
    $nfoPath = Join-Path $codeDir "$code.nfo"
    
    # 从数据库查询影片信息
    $query = "SELECT * FROM movies WHERE code = '$code'"
    try {
        $conn = New-Object System.Data.SQLite.SQLiteConnection
        $conn.ConnectionString = "Data Source=$dbPath"
        $conn.Open()
        
        $cmd = $conn.CreateCommand()
        $cmd.CommandText = $query
        $reader = $cmd.ExecuteReader()
        
        if ($reader.Read()) {
            Write-Host "  📊 找到数据库记录"
            
            # 构建 NFO 内容
            $nfoContent = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
  <title>$($reader['title'])</title>
  <code>$code</code>
"@
            
            if ($reader['release_date']) {
                $nfoContent += "`n  <releasedate>$($reader['release_date'])</releasedate>"
                $nfoContent += "`n  <year>$($reader['release_date'].Substring(0,4))</year>"
            }
            
            if ($reader['duration']) {
                $nfoContent += "`n  <runtime>$($reader['duration'])</runtime>"
            }
            
            if ($reader['studio']) {
                $studio = $reader['studio'] -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
                $nfoContent += "`n  <studio>$studio</studio>"
            }
            
            if ($reader['maker']) {
                $maker = $reader['maker'] -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
                $nfoContent += "`n  <maker>$maker</maker>"
            }
            
            if ($reader['director']) {
                $director = $reader['director'] -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
                $nfoContent += "`n  <director>$director</director>"
            }
            
            # 演员
            if ($reader['actors']) {
                $actors = $reader['actors'] -split ','
                foreach ($actor in $actors) {
                    $actor = $actor.Trim() -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
                    if ($actor) {
                        $nfoContent += "`n  <actor>`n    <name>$actor</name>`n    <type>Actress</type>`n  </actor>"
                    }
                }
            }
            
            # 标签
            if ($reader['genres']) {
                $genres = $reader['genres'] -split ','
                foreach ($genre in $genres) {
                    $genre = $genre.Trim() -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
                    if ($genre) {
                        $nfoContent += "`n  <genre>$genre</genre>"
                    }
                }
            }
            
            # 封面路径
            $fanartPath = Join-Path $codeDir "$code-fanart.jpg"
            $posterPath = Join-Path $codeDir "$code-poster.jpg"
            $nfoContent += "`n  <fanart>$fanartPath</fanart>"
            $nfoContent += "`n  <thumb>$posterPath</thumb>"
            
            # 本地视频路径
            $movieId = $reader['id']
            $localVideoId = $reader['local_video_id']
            if ($localVideoId) {
                $videoQuery = "SELECT path FROM local_videos WHERE id = $localVideoId"
                $cmd.CommandText = $videoQuery
                $videoPath = $cmd.ExecuteScalar()
                if ($videoPath) {
                    $videoPath = $videoPath -replace '&', '&amp;' -replace '<', '&lt;' -replace '>', '&gt;'
                    $nfoContent += "`n  <filenameandpath>$videoPath</filenameandpath>"
                }
            }
            
            $nfoContent += "`n</movie>"
            
            # 写入 NFO 文件
            $nfoContent | Out-File -FilePath $nfoPath -Encoding UTF8
            Write-Host "  ✅ NFO 生成成功: $code.nfo"
            $nfoCount++
        } else {
            Write-Host "  ⚠️ 数据库中未找到该番号"
        }
        
        $reader.Close()
        $conn.Close()
        
    } catch {
        Write-Host "  ⚠️ 数据库查询失败: $_"
    }
}

Write-Host "`n$('='*60)"
Write-Host "✨ 整理完成!"
Write-Host "  移动文件: $movedCount 个"
Write-Host "  生成 NFO: $nfoCount 个"
Write-Host "=" * 60
