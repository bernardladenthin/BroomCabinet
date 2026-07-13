<?php

// SPDX-FileCopyrightText: 2026 Bernard Ladenthin <bernard.ladenthin@gmail.com>
//
// SPDX-License-Identifier: Apache-2.0

// EXAMPLE ONLY — optional server-side receiver for the GPIO counter.
//
// gpiocounter.py can POST its per-minute value to a URL (see the commented-out
// "savevalue.php" hint in that script). This endpoint stores those values in
// MySQL and serves the history back as JSON for chart.html to draw.
//
// Replace the placeholder credentials below with your own and keep real secrets
// OUT of version control. CORS is wide open here for demo purposes — restrict it
// for any real deployment, and put the endpoint behind authentication.
//
// Save a value:   counter-endpoint.php?name=mysensor&value=102   (POST)
// Read history:   counter-endpoint.php?name=mysensor             (GET -> JSON)
// Create table:   counter-endpoint.php?createTable=1

header('Access-Control-Allow-Origin: *');

$mysql_server   = 'localhost';
$mysql_databse  = 'mydb';
$mysql_user     = 'dbuser';
$mysql_password = 'CHANGE_ME';

$tablename = "gpiocounter";

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

$isPost = isset($_REQUEST["value"]);

$maxLen = 255;

$name  = substr($_REQUEST['name'],  0, $maxLen); // name
$value  = substr($_REQUEST['value'],  0, $maxLen); // value
$limit = 60 * 24 * 10; // 10 days

$serverTime = time();

$createTable = boolval($_REQUEST['createTable']);
$dropTable = boolval($_REQUEST['dropTable']);

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
		$sql = "CREATE TABLE IF NOT EXISTS `".$tablename."` (
			`id`   INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
			`name`  TEXT,
			`value`  TEXT,
			`time` TEXT
			) ENGINE=MyISAM  DEFAULT CHARSET=utf8";

		if ($mysqli->query($sql) === TRUE) {
			echo "created";
		} else {
			echo "error during creation.";
		}

	} else if ($dropTable) {
		//$mysqli->query("DROP TABLE ".$tablename."");
		echo "dropped";
	} else if ($isPost) {
		$stmt = $mysqli->prepare('INSERT INTO '.$tablename.' (`name`, `value`, `time`) VALUES (?, ?, ?)');
		echo $mysqli->error;
		$stmt->bind_param('sss', $name, $value, $serverTime);
		$stmt->execute();
		$stmt->close();
	} else if($isGet) {
		$stmt = $mysqli->prepare('SELECT `id`, `name`, `value`, `time` from '.$tablename.' where name=(?) order by id desc limit '.$limit);
		$stmt->bind_param('s', $name);
		$stmt->execute();
		$stmt->bind_result($id, $name, $value, $time);

		$resultArray = [];
		while($stmt->fetch()) {
			$result = new stdClass();
			//$result->id=$id;
			//$result->name=$name;
			$result->value=$value;
			$result->time=$time;
			array_push($resultArray, $result);
		}
		$stmt->close();

		$resultWrapper = new stdClass();
		$resultWrapper->values = $resultArray;
		echo json_encode($resultWrapper);
	}
	$mysqli->close();

} catch (Exception $e) {
  echo $e->getMessage();
}

exit();
