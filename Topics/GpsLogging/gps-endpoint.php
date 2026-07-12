<?php
/**
 * Copyright 2026 Bernard Ladenthin bernard.ladenthin@gmail.com
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * EXAMPLE ONLY - a server-side receiver for the Android "GPSLogger" app.
 * Replace the placeholder DB credentials, keep real secrets OUT of version
 * control, and read the security notes in README.md before deploying.
 */

$requestTime = time();

// GPSLogger (Android) custom URL, e.g.:
// http://example.com/gps-endpoint.php?p&lat=%LAT&lon=%LON&desc=%DESC&sat=%SAT&alt=%ALT&spd=%SPD&acc=%ACC&dir=%DIR&prov=%PROV&time=%TIME&batt=%BATT&aid=%AID&ser=%SER
$mysql_server = 'localhost';
$mysql_databse = 'mydb';
$mysql_user = 'dbuser';
$mysql_password = 'CHANGE_ME';
$tablename = "gpstracker";

// Guard for the table create/drop actions below. Keep this false in production
// (see README) - otherwise any request with ?dropTable=1 can drop the table.
$enableCreateAndDrop = false;


// //////////////////////////////////////////////////
// REQUEST_METHOD
// //////////////////////////////////////////////////

$isPut = false;
$isPost = false;
$isGet = false;
$isHead = false;
$isDelete = false;
$isOptions = false;
$isDefault = false;

switch ($_SERVER['REQUEST_METHOD']) {
  case 'PUT':
    $isPut = true;
    break;
  case 'POST':
    $isPost = true;
    break;
  case 'GET':
    $isGet = true;
    break;
  case 'HEAD':
    $isHead = true;
    break;
  case 'DELETE':
    $isDelete = true;
    break;
  case 'OPTIONS':
    $isOptions = true;
    break;
  default:
    $isDefault = true;
    break;
}

// //////////////////////////////////////////////////
// request parameter
// //////////////////////////////////////////////////

$isPost = isset($_REQUEST["p"]);
$isGetAsCSV = boolval($_REQUEST["getAsCsv"]);
$isGetAsGPX = boolval($_REQUEST["getAsGpx"]);

$createTable = boolval($_REQUEST['createTable']);
$dropTable = boolval($_REQUEST['dropTable']);

$maxLen = 255;

// strings
$usertoken = substr($_REQUEST['usertoken'],  0, $maxLen); // usertoken

$lat       = substr($_REQUEST['lat'],        0, $maxLen); // latitude
$lon       = substr($_REQUEST['lon'],        0, $maxLen); // longitude
$desc      = substr($_REQUEST['desc'],       0, $maxLen); // description
$sat       = substr($_REQUEST['sat'],        0, $maxLen); // satellites
$alt       = substr($_REQUEST['alt'],        0, $maxLen); // altitude
$spd       = substr($_REQUEST['spd'],        0, $maxLen); // speed
$acc       = substr($_REQUEST['acc'],        0, $maxLen); // accuracy
$dir       = substr($_REQUEST['dir'],        0, $maxLen); // direction
$prov      = substr($_REQUEST['prov'],       0, $maxLen); // provider
$time      = substr($_REQUEST['time'],       0, $maxLen); // time
$batt      = substr($_REQUEST['batt'],       0, $maxLen); // battery
$aid       = substr($_REQUEST['aid'],        0, $maxLen); // Android id
$ser       = substr($_REQUEST['ser'],        0, $maxLen); // serial

// convert
$sat = intval($sat);

error_reporting(E_ALL);
mysqli_report(MYSQLI_REPORT_STRICT);

// http://php.net/manual/de/mysqli-stmt.bind-param.php
/*
Binds variables to prepared statement

i    corresponding variable has type integer
d    corresponding variable has type double
s    corresponding variable has type string
b    corresponding variable is a blob and will be sent in packets
*/
try {
	$mysqli = new mysqli($mysql_server, $mysql_user, $mysql_password, $mysql_databse);
	if ($createTable) {
        if ($enableCreateAndDrop) {
            $sql = "CREATE TABLE IF NOT EXISTS `".$tablename."` (
                `id`         INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `usertoken`  TEXT,
                `lat`        FLOAT,
                `lon`        FLOAT,
                `desc`       TEXT,
                `sat`        INT,
                `alt`        TEXT,
                `spd`        FLOAT,
                `acc`        FLOAT,
                `dir`        FLOAT,
                `prov`       TEXT,
                `time`       TEXT,
                `stime`      BIGINT,
                `batt`       FLOAT,
                `aid`        TEXT,
                `ser`        TEXT
                ) ENGINE=MyISAM DEFAULT CHARSET=utf8";

            $mysqli->query($sql);
            echo "created";
        } else {
            echo "created disabled";
        }
	} else if ($dropTable) {
        if ($enableCreateAndDrop) {
            $mysqli->query("DROP TABLE `".$tablename."`");
            echo "dropped";
        } else {
            echo "dropped disabled";
        }
	} else if ($isPost) {
		$stmt = $mysqli->prepare('INSERT INTO `'.$tablename.'` (`usertoken`, `lat`, `lon`, `desc`, `sat`, `alt`, `spd`, `acc`, `dir`, `prov`, `time`, `stime`, `batt`, `aid`, `ser`) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
		//echo $mysqli->error;
		$stmt->bind_param('sssssssssssssss', $usertoken, $lat, $lon, $desc, $sat, $alt, $spd, $acc, $dir, $prov, $time, $requestTime, $batt, $aid, $ser);
		$stmt->execute();
		$stmt->close();
	} else if($isGet) {
        if ($isGetAsCSV) {
            $stmt = $mysqli->prepare('SELECT `id`, `lat`, `lon`, `desc`, `sat`, `alt`, `spd`, `acc`, `dir`, `prov`, `time`, `stime`, `batt`, `aid`, `ser` from `'.$tablename.'` where usertoken = ? order by id');
		    $stmt->bind_param('s', $usertoken);
            $stmt->execute();
            $stmt->bind_result($id, $lat, $lon, $desc, $sat, $alt, $spd, $acc, $dir, $prov, $time, $requestTime, $batt, $aid, $ser);
            $output = fopen("php://output",'w') or die("Can't open php://output");
            fputcsv($output, array('id', 'lat', 'lon', 'desc', 'sat', 'alt', 'spd', 'acc', 'dir', 'prov', 'time', 'stime', 'batt', 'aid', 'ser'));
            while ($stmt->fetch()) {
                fputcsv($output, array($id, $lat, $lon, $desc, $sat, $alt, $spd, $acc, $dir, $prov, $time, $requestTime, $batt, $aid, $ser));
            }
            $stmt->close();
            fclose($output) or die("Can't close php://output");
        } else if($isGetAsGPX) {
            $stmt = $mysqli->prepare('SELECT `id`, `lat`, `lon`, `desc`, `sat`, `alt`, `spd`, `acc`, `dir`, `prov`, `time`, `stime`, `batt`, `aid`, `ser` from `'.$tablename.'` where usertoken = ? order by id');
		    $stmt->bind_param('s', $usertoken);
            $stmt->execute();
            $stmt->bind_result($id, $lat, $lon, $desc, $sat, $alt, $spd, $acc, $dir, $prov, $time, $requestTime, $batt, $aid, $ser);
            header("Content-Type: text/xml");
            echo '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>';
            echo '<gpx version="1.1" creator="gpslogger">';
                echo '<metadata> <!-- metadata --> </metadata>';
                echo '<rte>';
                    echo '<name>'.$usertoken.'</name>';
                    while ($stmt->fetch()) {
                        echo '<rtept lon="'.$lon.'" lat="'.$lat.'">';
                            echo '<name>'.$id.'</name>';
                            echo '<sat>'.intval($sat).'</sat>';
                            echo '<src>'.$prov.'</src>';
                            echo '<pdop>'.$acc.'</pdop>';
                            echo '<time>'.$time.'</time>';
                            echo '<desc>'.$desc.', batt: '.$batt.'</desc>';
                            echo '<geoidheight>'.$alt.'</geoidheight>';
                        echo '</rtept>';
                        echo '';
                        //$spd, $dir, $requestTime, $aid, $ser
                    }
                $stmt->close();
                echo '</rte>';
            echo '</gpx>';
        } else {
            $stmt = $mysqli->prepare('SELECT `id`, `lat`, `lon`, `desc`, `sat`, `alt`, `spd`, `acc`, `dir`, `prov`, `time`, `stime`, `batt`, `aid`, `ser` from `'.$tablename.'` where usertoken = ? order by id desc limit 1');
		    $stmt->bind_param('s', $usertoken);
            $stmt->execute();
            $stmt->bind_result($id, $lat, $lon, $desc, $sat, $alt, $spd, $acc, $dir, $prov, $time, $requestTime, $batt, $aid, $ser);
            $stmt->fetch();
            $stmt->close();

            $result = new stdClass();
            $result->id=$id;
            $result->lat=$lat;
            $result->lon=$lon;
            $result->desc=$desc;
            $result->sat=$sat;
            $result->alt=$alt;
            $result->spd=$spd;
            $result->acc=$acc;
            $result->dir=$dir;
            $result->prov=$prov;
            $result->time=$time;
            $result->stime=$requestTime;
            $result->batt=$batt;
            $result->aid=$aid;
            $result->ser=$ser;
            echo json_encode($result);
        }
	}
	$mysqli->close();

} catch (Exception $e) {
  echo $e->getMessage();
}

exit();
