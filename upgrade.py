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

def findFile(path, findFileFilter):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            if findFileFilter(root, name):
                return os.path.join(root, name)


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


def writeEmbeddingV1Activity(mainActivityPath):
    pluginInfo = getPluginInfo(mainActivityPath)
    splitPath = list(os.path.split(mainActivityPath))
    splitPath[-1] = "EmbeddingV1Activity.java"
    v1ActivityPath = apply(os.path.join, splitPath)
    print("writing: " + v1ActivityPath)
    with open(v1ActivityPath, "w") as f:
        f.write(
            g_embeddingV1Activity.replace("TEMPLATE_PACKAGE",
                                          pluginInfo["package"]))


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

    dependenciesMatch = re.search("dependencies.*\{", text, re.MULTILINE)
    if dependenciesMatch:
        text = text[:dependenciesMatch.end()] + g_exampleAppDependencies + text[dependenciesMatch.end():]
    else:
        text = text + "dependencies {\n" + g_exampleAppDependencies + "}\n"

    with open(exampleAppBuildGradlePath, "w") as f:
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
    upgradeMainActivity(mainActivityPath, pluginInfo)

    ##################
    # Step 6
    ##################
    writeEmbeddingV1Activity(mainActivityPath)

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

if __name__ == "__main__":
    main()
