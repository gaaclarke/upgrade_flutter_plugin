"""
Attempt to automate steps found in:
https://github.com/flutter/flutter/wiki/Experimental:-Create-Flutter-Plugin

usage: upgrade.py <path to flutter plugin directory>
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import os
import re

g_attachDetachStubs = """
  @Override
  public void onAttachedToEngine(@NonNull FlutterPluginBinding binding) {
    // TODO: your plugin is now attached to a Flutter experience.
  }

  @Override
  public void onDetachedFromEngine(@NonNull FlutterPluginBinding binding) {
    // TODO: your plugin is no longer attached to a Flutter experience.
  }
"""

g_mainActivityFormat = """
import io.flutter.embedding.android.FlutterActivity;
import io.flutter.embedding.engine.FlutterEngine;
import TEMPLATE_PACKAGE.TEMPLATE_CLASS;

public class MainActivity extends FlutterActivity {
  // TODO(<github-username>): Remove this once v2 of GeneratedPluginRegistrant rolls to stable. https://github.com/flutter/flutter/issues/42694
  @Override
  public void configureFlutterEngine(FlutterEngine flutterEngine) {
    flutterEngine.getPlugins().add(new TEMPLATE_CLASS());
  }
}
"""

g_embeddingV1Activity = """
package TEMPLATE_PACKAGE;

import android.os.Bundle;
import io.flutter.app.FlutterActivity;
import io.flutter.plugins.GeneratedPluginRegistrant;

public class EmbeddingV1Activity extends FlutterActivity {
 @Override
 protected void onCreate(Bundle savedInstanceState) {
   super.onCreate(savedInstanceState);
   GeneratedPluginRegistrant.registerWith(this);
 }
}
"""

g_exampleManifestActivity = """<activity
    android:name=".EmbeddingV1Activity"
    android:theme="@style/LaunchTheme"
         android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|layoutDirection|fontScale"
    android:hardwareAccelerated="true"
    android:windowSoftInputMode="adjustResize">
</activity>
"""

g_gradleScript = """
// TODO(<github-username>): Remove this hack once androidx.lifecycle is included on stable. https://github.com/flutter/flutter/issues/42348
afterEvaluate {
    def containsEmbeddingDependencies = false
    for (def configuration : configurations.all) {
        for (def dependency : configuration.dependencies) {
            if (dependency.group == 'io.flutter' &&
                    dependency.name.startsWith('flutter_embedding') &&
                    dependency.isTransitive())
            {
                containsEmbeddingDependencies = true
                break
            }
        }
    }
    if (!containsEmbeddingDependencies) {
        android {
            dependencies {
                def lifecycle_version = "1.1.1"
                compileOnly "android.arch.lifecycle:runtime:$lifecycle_version"
                compileOnly "android.arch.lifecycle:common:$lifecycle_version"
                compileOnly "android.arch.lifecycle:common-java8:$lifecycle_version"
            }
        }
    }
}
"""

g_exampleAppDependencies = """
androidTestImplementation 'androidx.test:runner:1.2.0'
androidTestImplementation 'androidx.test:rules:1.2.0'
androidTestImplementation 'androidx.test.espresso:espresso-core:3.2.0'
"""

g_mainActivityTest = """
package TEMPLATE_PACKAGE;

import androidx.test.rule.ActivityTestRule;
import dev.flutter.plugins.e2e.FlutterRunner;
import TEMPLATE_MAIN_ACTIVITY_PACKAGE.MainActivity;
import org.junit.Rule;
import org.junit.runner.RunWith;

@RunWith(FlutterRunner.class)
public class MainActivityTest {
  @Rule public ActivityTestRule<MainActivity> rule = new ActivityTestRule<>(MainActivity.class);
}
"""

g_embeddingV1ActivityTest = """
package TEMPLATE_PACKAGE;

import androidx.test.rule.ActivityTestRule;
import dev.flutter.plugins.e2e.FlutterRunner;
import TEMPLATE_MAIN_ACTIVITY_PACKAGE.EmbeddingV1Activity;
import org.junit.Rule;
import org.junit.runner.RunWith;

@RunWith(FlutterRunner.class)
public class EmbeddingV1ActivityTest {
  @Rule
  public ActivityTestRule<EmbeddingV1Activity> rule =
      new ActivityTestRule<>(EmbeddingV1Activity.class);
}
"""

g_minFlutterVersion = [
  '  sdk: ">=2.0.0-dev.28.0 <3.0.0"',
  '  flutter: ">=1.9.1+hotfix.5 <2.0.0"'
]

g_dartTestStub = """
import 'package:flutter_test/flutter_test.dart';
import 'package:e2e/e2e.dart';

void main() {
  E2EWidgetsFlutterBinding.ensureInitialized();

  testWidgets('some test', (WidgetTester tester) async {
    // TODO: write test
  });
}
"""

def findFile(path, findFileFilter):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            if findFileFilter(root, name):
                return os.path.join(root, name)

def strInsert(aString, insertLoc, insertValue):
    return aString[:insertLoc] + insertValue + aString[insertLoc:]

def insertItems(lst, items):
    for item in items:
        lst.append(item)

def upgradePluginJava(pluginPath):
    text = ""
    with open(pluginPath) as f:
        text = f.read()
    # imports
    importIndex = text.find("\nimport ")
    if text.find("io.flutter.embedding.engine.plugins.FlutterPlugin") < 0:
        text = text[:
                    importIndex] + "\nimport io.flutter.embedding.engine.plugins.FlutterPlugin;" + text[
                        importIndex:]
    if text.find("android.support.annotation.NonNull") < 0:
        text = text[:
                    importIndex] + "\nimport android.support.annotation.NonNull;" + text[
                        importIndex:]
    # implements
    text = re.sub("implements MethodCallHandler",
                  "implements FlutterPlugin, MethodCallHandler", text)
    insideClassLoc = re.search("implements.*FlutterPlugin.*\{", text,
                               re.MULTILINE).end()
    text = text[:insideClassLoc] + g_attachDetachStubs + text[insideClassLoc:]

    with open(pluginPath, "w") as f:
        f.write(text)


def getPluginInfo(pluginPath):
    text = ""
    with open(pluginPath) as f:
        text = f.read()
    nameMatch = re.search("class\s*(.*Plugin)\s", text)
    packageMatch = re.search("package (.*);", text)
    return {
        "package": packageMatch.group(1),
        "name": nameMatch.group(1) if nameMatch else None
    }


def upgradeMainActivity(mainActivityPath, pluginInfo):
    text = ""
    with open(mainActivityPath) as f:
        text = f.read()

    importIndex = text.find("\nimport ")
    text = text[:importIndex] + g_mainActivityFormat.replace(
        "TEMPLATE_PACKAGE", pluginInfo["package"]).replace(
            "TEMPLATE_CLASS", pluginInfo["name"])

    with open(mainActivityPath, "w") as f:
        f.write(text)


def writeEmbeddingV1Activity(mainActivityPath, mainActivityInfo):
    splitPath = list(os.path.split(mainActivityPath))
    splitPath[-1] = "EmbeddingV1Activity.java"
    v1ActivityPath = os.path.join(*splitPath)
    print("writing: " + v1ActivityPath)
    with open(v1ActivityPath, "w") as f:
        f.write(
            g_embeddingV1Activity.replace("TEMPLATE_PACKAGE",
                                          mainActivityInfo["package"]))


def upgradeExampleManifest(exampleManifestPath):
    text = ""
    with open(exampleManifestPath) as f:
        text = f.read()

    activityIndex = text.find("<activity")
    text = text[:activityIndex] + g_exampleManifestActivity + text[
        activityIndex:]

    with open(exampleManifestPath, "w") as f:
        f.write(text)


def upgradePluginBuildGradle(pluginBuildGradlePath):
    text = ""
    with open(pluginBuildGradlePath) as f:
        text = f.read()

    text = text + g_gradleScript

    with open(pluginBuildGradlePath, "w") as f:
        f.write(text)

def upgradeExampleAppBuildGradle(exampleAppBuildGradlePath):
    text = ""
    with open(exampleAppBuildGradlePath) as f:
        text = f.read()

    text = text.replace("android.support.test.runner.AndroidJUnitRunner",
                        "androidx.test.runner.AndroidJUnitRunner")
    dependenciesMatch = re.search(r"dependencies.*\{", text, re.MULTILINE)
    if dependenciesMatch:
        text = text[:dependenciesMatch.end()] + g_exampleAppDependencies + text[dependenciesMatch.end():]
    else:
        text = text + "dependencies {\n" + g_exampleAppDependencies + "}\n"

    with open(exampleAppBuildGradlePath, "w") as f:
        f.write(text)

def writeTestFiles(testPath, mainActivityInfo, pluginInfo):
    package = pluginInfo["package"]
    fullPath = os.path.join(*([testPath] + package.split(".")))
    if not os.path.exists(fullPath):
        os.makedirs(fullPath)
    with open(os.path.join(fullPath, "MainActivityTest.java"), "w") as f:
        f.write(g_mainActivityTest.replace(
            "TEMPLATE_PACKAGE", package).replace(
                "TEMPLATE_MAIN_ACTIVITY_PACKAGE", mainActivityInfo["package"]))
    with open(os.path.join(fullPath, "EmbeddingV1ActivityTest.java"), "w") as f:
        f.write(g_embeddingV1ActivityTest.replace(
            "TEMPLATE_PACKAGE", package).replace(
                "TEMPLATE_MAIN_ACTIVITY_PACKAGE", mainActivityInfo["package"]))

def addDevDependencies(pubspecPath):
    text = ""
    with open(pubspecPath) as f:
        text = f.read()

    devDependenciesMatch = re.search(r"dev_dependencies:.*\n(\s*)", text, re.MULTILINE)
    indent = devDependenciesMatch.group(1)
    devDependenciesEnd = devDependenciesMatch.end()

    if text.find("e2e:") < 0:
        text = strInsert(text, devDependenciesEnd, "e2e: ^0.2.1\n" + indent)

    if text.find("flutter_driver:") < 0:
        text = strInsert(text, devDependenciesEnd, "flutter_driver:\n" + indent + "  sdk: flutter\n" + indent)

    with open(pubspecPath, "w") as f:
        text = f.write(text)

def updatePubspecsDevDependencies(pubspecPath, examplePubspecPath):
    addDevDependencies(pubspecPath)
    addDevDependencies(examplePubspecPath)

def updateMinFlutterVersion(pubspecPath):
    text = ""
    with open(pubspecPath) as f:
        text = f.read()

    newLines = []
    inEnvironment = False
    for line in text.split("\n"):
        if line.rstrip() == "environment:":
            inEnvironment = True
            newLines.append(line)
        elif inEnvironment:
            if line == "" or not line[0].isspace():
                inEnvironment = False
                insertItems(newLines, g_minFlutterVersion)
                newLines.append(line)
            else:
                pass # Intentionally skip line.
        else:
            newLines.append(line)

    if inEnvironment:
        insertItems(newLines, g_minFlutterVersion)

    with open(pubspecPath, "w") as f:
        text = f.write("\n".join(newLines))

def writeDartTest(path):
    with open(path, "w") as f:
        f.write(g_dartTestStub)

def addE2EPlugin(mainActivityPath):
    text = ""
    with open(mainActivityPath) as f:
        text = f.read()

    importMatch = re.search("import .*", text)
    text = strInsert(text, importMatch.start(),
                     "import dev.flutter.plugins.e2e.E2EPlugin;\n")
    addPluginMatch = re.search(
        r"(\s*)flutterEngine\.getPlugins\(\)\.add\(.*", text)
    text = strInsert(text,
                     addPluginMatch.start(),
                     addPluginMatch.group(1) + "flutterEngine.getPlugins().add(new E2EPlugin());")

    with open(mainActivityPath, "w") as f:
        f.write(text)

def main():
    if len(sys.argv) != 2:
        print("usage: upgrade.py <path to plugin directory>")
        sys.exit(1)
    pluginDirPath = sys.argv[1]

    ##################
    # Step 1
    ##################
    pluginPath = findFile(pluginDirPath,
                          lambda root, name: name.find("Plugin.java") >= 0)
    if not pluginPath:
        print("unable to find plugin.")
        sys.exit(1)
    print("upgrading: " + pluginPath)
    upgradePluginJava(pluginPath)

    ##################
    # Step 4
    ##################
    mainActivityPath = findFile(
        pluginDirPath, lambda root, name: name.find("MainActivity.java") >= 0)
    print("upgrading: " + mainActivityPath)
    pluginInfo = getPluginInfo(pluginPath)
    mainActivityInfo = getPluginInfo(mainActivityPath)
    upgradeMainActivity(mainActivityPath, pluginInfo)

    ##################
    # Step 6
    ##################
    writeEmbeddingV1Activity(mainActivityPath, mainActivityInfo)

    ##################
    # Step 7
    ##################
    exampleManifestPath = findFile(
        pluginDirPath, lambda root, name: name.find("AndroidManifest.xml") == 0
        and root.find("example") >= 0)
    print("upgrading: " + exampleManifestPath)
    upgradeExampleManifest(exampleManifestPath)

    ##################
    # Step 8
    ##################
    pluginBuildGradlePath = findFile(
        pluginDirPath, lambda root, name: name.find("build.gradle") == 0 and
        root.find("example") < 0)
    print("upgrading: " + pluginBuildGradlePath)
    upgradePluginBuildGradle(pluginBuildGradlePath)

    ##################
    # Step 9
    ##################
    exampleAppBuildGradlePath = findFile(
        pluginDirPath, lambda root, name: name.find("build.gradle") == 0 and
        root.find("example") >= 0 and root.find("app") >= 0)
    print("upgrading: "+ exampleAppBuildGradlePath)
    upgradeExampleAppBuildGradle(exampleAppBuildGradlePath)

    ##################
    # Step 10
    ##################
    testDir = "example/android/app/src/androidTest/java"
    fullTestDir = os.path.join(pluginDirPath, testDir)
    writeTestFiles(fullTestDir, mainActivityInfo, pluginInfo)

    ###################
    # Step 11
    ###################
    pubspecPath = findFile(pluginDirPath, lambda root, name: name == "pubspec.yaml" and root.find("example") < 0)
    examplePubspecPath = findFile(pluginDirPath, lambda root, name: name == "pubspec.yaml" and root.find("example") >= 0)
    print("upgrading: " + pubspecPath)
    print("upgrading: " + examplePubspecPath)
    updatePubspecsDevDependencies(pubspecPath, examplePubspecPath)

    ###################
    # Step 12
    ###################
    print("upgrading: " + mainActivityPath)
    addE2EPlugin(mainActivityPath)

    ###################
    # Step 13
    ###################
    updateMinFlutterVersion(pubspecPath)

    ###################
    # Step 14
    ###################
    dirName = os.path.basename(os.path.abspath(pluginDirPath))
    dartTestPath = os.path.join(pluginDirPath, "test", "%s_e2e.dart" % dirName)
    if not os.path.exists(dartTestPath):
        print("writing: " + dartTestPath)
        writeDartTest(dartTestPath)

if __name__ == "__main__":
    main()
