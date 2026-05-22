allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

// Send every module's build output to the shared /build folder at the project root.
rootProject.layout.buildDirectory.set(file("${project.projectDir}/../build"))

subprojects {
    val newSubprojectBuildDir = rootProject.layout.buildDirectory.dir(project.name)
    project.layout.buildDirectory.set(newSubprojectBuildDir)
}

subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}